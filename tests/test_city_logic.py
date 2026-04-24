import json
import tempfile
import unittest
from pathlib import Path

from config import load_allowed_chats
from services.city_catalog_service import CityCatalog, paginate_items, total_pages
from services.city_service import CityRepository


class CityRepositoryTests(unittest.TestCase):
  def test_upsert_user_city_creates_city_file_and_updates_player(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      catalog = CityCatalog(temp_dir)
      repository = CityRepository(catalog)

      repository.upsert_user_city("mahjong", "Москва", 100, display_name="Ivan", username="ivan")
      repository.upsert_user_city("mahjong", "Москва", 100, display_name="Ivan Petrov", username="ivan")

      city = repository.get_city("mahjong", "Москва")

      self.assertIsNotNone(city)
      self.assertEqual(len(city.players), 1)
      self.assertEqual(city.players[0].display_name, "Ivan Petrov")
      self.assertEqual(city.players[0].username, "ivan")

  def test_upsert_user_city_moves_user_between_cities(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      catalog = CityCatalog(temp_dir)
      repository = CityRepository(catalog)

      repository.upsert_user_city("mahjong", "Москва", 100, display_name="Ivan", username="ivan")
      repository.upsert_user_city("mahjong", "Казань", 100, display_name="Ivan", username="ivan")

      self.assertEqual(repository.find_city_by_user_id("mahjong", 100), "Казань")
      self.assertIsNone(repository.get_city("mahjong", "Москва"))

  def test_rename_city_merges_players(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      catalog = CityCatalog(temp_dir)
      repository = CityRepository(catalog)

      repository.upsert_user_city("mahjong", "Москва", 1, display_name="One", username="one")
      repository.upsert_user_city("mahjong", "Питер", 2, display_name="Two", username="two")
      repository.rename_city("mahjong", "Питер", "Москва")

      city = repository.get_city("mahjong", "Москва")
      self.assertIsNotNone(city)
      self.assertCountEqual([player.user_id for player in city.players], [1, 2])


class CityCatalogTests(unittest.TestCase):
  def test_catalog_loads_city_files_from_context_folder(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      context_dir = Path(temp_dir) / "cities_mahjong"
      context_dir.mkdir()
      city_file = context_dir / "moskva.json"
      city_file.write_text(
        json.dumps(
          {
            "name": "Москва",
            "auto_show_members": False,
            "clubs": [{"title": "Фурин", "url": "https://example.com", "visible": False}],
            "players": [{"user_id": 1, "display_name": "Ivan"}],
          },
          ensure_ascii=False,
        ),
        encoding="utf-8",
      )

      catalog = CityCatalog(temp_dir)
      city = catalog.get_city("mahjong", "Москва")

      self.assertIsNotNone(city)
      self.assertFalse(city.auto_show_members)
      self.assertEqual(city.clubs[0].title, "Фурин")
      self.assertFalse(city.clubs[0].visible)
      self.assertEqual(city.players[0].user_id, 1)

  def test_pagination_helpers(self):
    items = [str(index) for index in range(25)]
    self.assertEqual(total_pages(items, 12), 3)
    self.assertEqual(paginate_items(items, 1, 12), [str(index) for index in range(12, 24)])


class ChatsConfigTests(unittest.TestCase):
  def test_load_allowed_chats_reads_context_format(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      config_path = Path(temp_dir) / "chats.json"
      config_path.write_text(
        json.dumps(
          {
            "contexts": {
              "mahjong": {"chat_ids": ["-1"]},
              "test": {"chat_ids": ["-2", "-3"]},
            }
          }
        ),
        encoding="utf-8",
      )

      import config as config_module

      old_path = config_module.CHATS_FILE
      config_module.CHATS_FILE = config_path
      try:
        mapping = load_allowed_chats()
      finally:
        config_module.CHATS_FILE = old_path

      self.assertEqual(mapping["-1"], "mahjong")
      self.assertEqual(mapping["-2"], "test")
      self.assertEqual(mapping["-3"], "test")


if __name__ == "__main__":
  unittest.main()

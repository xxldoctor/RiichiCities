import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from services.city_catalog_service import CityCatalog, CityInfo, CityPlayer


class CityRepository:
  def __init__(self, city_catalog: CityCatalog):
    self.city_catalog = city_catalog

  def list_meta_ids(self) -> List[str]:
    return self.city_catalog.list_meta_ids()

  def load_cities(self, meta_id: str) -> Dict[str, CityInfo]:
    return self.city_catalog.load(meta_id)

  def get_city(self, meta_id: str, city_name: str) -> Optional[CityInfo]:
    return self.city_catalog.get_city(meta_id, city_name)

  def get_city_names(self, meta_id: str) -> List[str]:
    return sorted(self.load_cities(meta_id).keys())

  def get_chat_data(self, meta_id: str) -> Dict[str, CityInfo]:
    return self.load_cities(meta_id)

  def get_city_players(self, meta_id: str, city_name: str) -> List[CityPlayer]:
    city = self.get_city(meta_id, city_name)
    if city is None:
      return []
    return list(city.players)

  def find_city_by_user_id(self, meta_id: str, user_id: int) -> Optional[str]:
    for city_name, city_info in self.load_cities(meta_id).items():
      if any(player.user_id == user_id for player in city_info.players):
        return city_name
    return None

  def find_player(self, meta_id: str, lookup_token: str) -> Optional[CityPlayer]:
    normalized_token = lookup_token.lower()
    for city_info in self.load_cities(meta_id).values():
      for player in city_info.players:
        if normalized_token.startswith("id:") and player.user_id is not None:
          if normalized_token == f"id:{player.user_id}".lower():
            return player
        if player.username and player.username.lower() == normalized_token:
          return player
    return None

  def find_meta_ids_by_user(self, user_id: int) -> List[str]:
    found_meta_ids: List[str] = []
    for meta_id in self.list_meta_ids():
      if self.find_city_by_user_id(meta_id, user_id) is not None:
        found_meta_ids.append(meta_id)
    return found_meta_ids

  def user_exists_in_meta(self, meta_id: str, user_id: int) -> bool:
    return self.find_city_by_user_id(meta_id, user_id) is not None

  def _save_city(self, meta_id: str, city_info: CityInfo) -> None:
    target_dir = self.city_catalog.context_dir(meta_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{self.city_catalog.slugify(city_info.name)}.json"
    payload = asdict(city_info)
    with open(target_path, "w", encoding="utf-8") as file:
      json.dump(payload, file, ensure_ascii=False, indent=2)

  def _delete_city_file(self, meta_id: str, city_name: str) -> None:
    target_path = self.city_catalog.context_dir(meta_id) / f"{self.city_catalog.slugify(city_name)}.json"
    if target_path.exists():
      target_path.unlink()

  def ensure_city(self, meta_id: str, city_name: str) -> CityInfo:
    existing = self.get_city(meta_id, city_name)
    if existing is not None:
      return existing

    city_info = CityInfo(name=city_name)
    self._save_city(meta_id, city_info)
    return city_info

  def upsert_user_city(
    self,
    meta_id: str,
    city_name: str,
    user_id: int,
    display_name: Optional[str] = None,
    username: Optional[str] = None,
  ) -> None:
    old_city_name = self.find_city_by_user_id(meta_id, user_id)
    if old_city_name is not None and old_city_name != city_name:
      self.remove_user_from_city(meta_id, old_city_name, user_id)

    city_info = self.ensure_city(meta_id, city_name)
    existing_player = next((player for player in city_info.players if player.user_id == user_id), None)
    if existing_player is None:
      city_info.players.append(
        CityPlayer(
          user_id=user_id,
          display_name=display_name,
          username=username,
        )
      )
    else:
      existing_player.display_name = display_name or existing_player.display_name
      existing_player.username = username or existing_player.username

    self._save_city(meta_id, city_info)

  def remove_user_from_city(self, meta_id: str, city_name: str, user_id: int) -> bool:
    city_info = self.get_city(meta_id, city_name)
    if city_info is None:
      return False

    original_count = len(city_info.players)
    city_info.players = [player for player in city_info.players if player.user_id != user_id]
    if len(city_info.players) == original_count:
      return False

    if not city_info.players and not city_info.clubs and not city_info.ratings and not city_info.users_text and not city_info.join_error_text:
      self._delete_city_file(meta_id, city_name)
    else:
      self._save_city(meta_id, city_info)
    return True

  def rename_city(self, meta_id: str, old_city: str, new_city: str) -> bool:
    old_city_info = self.get_city(meta_id, old_city)
    if old_city_info is None:
      return False

    if old_city == new_city:
      return True

    new_city_info = self.get_city(meta_id, new_city)
    if new_city_info is None:
      old_city_info.name = new_city
      self._delete_city_file(meta_id, old_city)
      self._save_city(meta_id, old_city_info)
      return True

    existing_ids = {player.user_id for player in new_city_info.players if player.user_id is not None}
    for player in old_city_info.players:
      if player.user_id is None or player.user_id not in existing_ids:
        new_city_info.players.append(player)

    if not new_city_info.users_text:
      new_city_info.users_text = old_city_info.users_text
    if not new_city_info.join_error_text:
      new_city_info.join_error_text = old_city_info.join_error_text
    if old_city_info.auto_show_members is False:
      new_city_info.auto_show_members = False

    self._delete_city_file(meta_id, old_city)
    self._save_city(meta_id, new_city_info)
    return True

  def remove_city(self, meta_id: str, city_name: str) -> bool:
    if self.get_city(meta_id, city_name) is None:
      return False

    self._delete_city_file(meta_id, city_name)
    return True

  def get_all(self) -> Dict[str, Dict[str, CityInfo]]:
    return {meta_id: self.load_cities(meta_id) for meta_id in self.list_meta_ids()}

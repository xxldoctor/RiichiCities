import json
from typing import Dict, List, Optional


class CityRepository:
  def __init__(self, data_file: str):
    self.data_file = data_file
    self.city_users = self._load_data_from_file()

  def _load_data_from_file(self) -> Dict[str, Dict[str, List[int]]]:
    try:
      with open(self.data_file, "r", encoding="utf-8") as file:
        data = json.load(file)
    except FileNotFoundError:
      data = {}

    return {str(key): value for key, value in data.items()}

  def save(self) -> None:
    with open(self.data_file, "w", encoding="utf-8") as file:
      json.dump({str(key): value for key, value in self.city_users.items()}, file)

  def get_all(self) -> Dict[str, Dict[str, List[int]]]:
    return self.city_users

  def get_chat_data(self, meta_id: str) -> Dict[str, List[int]]:
    return self.city_users.get(meta_id, {})

  def set_chat_data(self, meta_id: str, chat_data: Dict[str, List[int]]) -> None:
    self.city_users[meta_id] = chat_data
    self.save()

  def user_exists_in_meta(self, meta_id: str, user_id: int) -> bool:
    for users in self.city_users.get(meta_id, {}).values():
      if user_id in users:
        return True
    return False

  def remove_user_from_city(self, meta_id: str, city: str, user_id: int) -> bool:
    chat_data = self.city_users.get(meta_id, {})

    if city not in chat_data:
      return False

    users_ids = chat_data[city]
    if user_id not in users_ids:
      return False

    users_ids.remove(user_id)
    if not chat_data[city]:
      del chat_data[city]

    self.city_users[meta_id] = chat_data
    self.save()
    return True

  def find_city_by_user_id(self, meta_id: str, user_id: int) -> Optional[str]:
    chat_data = self.city_users.get(meta_id, {})
    return next((city for city, users in chat_data.items() if user_id in users), None)

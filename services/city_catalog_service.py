import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CityLink:
  title: str
  url: str
  visible: bool = True


@dataclass
class CityPlayer:
  user_id: Optional[int] = None
  display_name: Optional[str] = None
  username: Optional[str] = None
  note: Optional[str] = None


@dataclass
class CityInfo:
  name: str
  visible: bool = True
  auto_show_members: bool = True
  users_text: Optional[str] = None
  join_error_text: Optional[str] = None
  clubs: List[CityLink] = field(default_factory=list)
  ratings: List[CityLink] = field(default_factory=list)
  players: List[CityPlayer] = field(default_factory=list)
  file_name: Optional[str] = field(default=None, repr=False, compare=False)


class CityCatalog:
  def __init__(self, base_dir: str):
    self.base_dir = Path(base_dir)

  def context_dir(self, meta_id: str) -> Path:
    return self.base_dir / f"cities_{meta_id}"

  def list_meta_ids(self) -> List[str]:
    meta_ids: List[str] = []
    for path in self.base_dir.glob("cities_*"):
      if path.is_dir():
        meta_ids.append(path.name[7:])
    return sorted(meta_ids)

  def city_key(self, text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()

  def file_name_for_city(self, city_name: str) -> str:
    forbidden_chars = '<>:"/\\|?*'
    safe_name = "".join("_" if char in forbidden_chars else char for char in city_name.strip())
    return f"{safe_name or 'city'}.json"

  def _load_city_file(self, path: Path) -> Optional[CityInfo]:
    with open(path, "r", encoding="utf-8-sig") as file:
      raw = json.load(file)

    city_name = raw.get("name")
    if not city_name:
      return None

    return CityInfo(
      name=city_name,
      visible=raw.get("visible", True),
      auto_show_members=raw.get("auto_show_members", True),
      users_text=raw.get("users_text"),
      join_error_text=raw.get("join_error_text"),
      clubs=[
        CityLink(
          title=item["title"],
          url=item["url"],
          visible=item.get("visible", True),
        )
        for item in raw.get("clubs", [])
      ],
      ratings=[
        CityLink(
          title=item["title"],
          url=item["url"],
          visible=item.get("visible", True),
        )
        for item in raw.get("ratings", [])
      ],
      players=[
        CityPlayer(
          user_id=item.get("user_id"),
          display_name=item.get("display_name"),
          username=item.get("username"),
          note=item.get("note"),
        )
        for item in raw.get("players", [])
      ],
      file_name=path.name,
    )

  def load(self, meta_id: str) -> Dict[str, CityInfo]:
    cities_dir = self.context_dir(meta_id)
    if not cities_dir.exists():
      return {}

    cities: Dict[str, CityInfo] = {}
    for path in sorted(cities_dir.glob("*.json")):
      city_info = self._load_city_file(path)
      if city_info is not None:
        cities[city_info.name] = city_info

    return cities

  def get_city(self, meta_id: str, city_name: str) -> Optional[CityInfo]:
    resolved_name = self.resolve_city_name(meta_id, city_name)
    if resolved_name is None:
      return None
    return self.load(meta_id).get(resolved_name)

  def resolve_city_name(self, meta_id: str, city_name: str) -> Optional[str]:
    target_key = self.city_key(city_name)
    for existing_city_name in self.load(meta_id).keys():
      if self.city_key(existing_city_name) == target_key:
        return existing_city_name
    return None


def paginate_items(items: List[str], page: int, page_size: int) -> List[str]:
  start = page * page_size
  end = start + page_size
  return items[start:end]


def total_pages(items: List[str], page_size: int) -> int:
  if not items:
    return 1
  return (len(items) + page_size - 1) // page_size

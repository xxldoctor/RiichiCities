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
  auto_show_members: bool = True
  users_text: Optional[str] = None
  join_error_text: Optional[str] = None
  clubs: List[CityLink] = field(default_factory=list)
  ratings: List[CityLink] = field(default_factory=list)
  players: List[CityPlayer] = field(default_factory=list)


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

  def slugify(self, text: str) -> str:
    translit_map = {
      "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
      "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
      "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
      "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    lowered = text.lower()
    chars = []
    for char in lowered:
      if char in translit_map:
        chars.append(translit_map[char])
      elif char.isascii() and char.isalnum():
        chars.append(char)
      else:
        chars.append("-")

    slug = "".join(chars)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "city"

  def _load_city_file(self, path: Path) -> Optional[CityInfo]:
    with open(path, "r", encoding="utf-8-sig") as file:
      raw = json.load(file)

    city_name = raw.get("name")
    if not city_name:
      return None

    return CityInfo(
      name=city_name,
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
    return self.load(meta_id).get(city_name)


def paginate_items(items: List[str], page: int, page_size: int) -> List[str]:
  start = page * page_size
  end = start + page_size
  return items[start:end]


def total_pages(items: List[str], page_size: int) -> int:
  if not items:
    return 1
  return (len(items) + page_size - 1) // page_size

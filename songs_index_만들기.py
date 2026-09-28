"""songs 폴더의 .osz 파일 목록을 songs/index.json 으로 만듭니다.
곡을 추가/삭제한 뒤 이 파일을 실행(더블클릭 또는 python songs_index_만들기.py)하고, 폴더를 다시 업로드하세요."""
import json
from pathlib import Path

base = Path(__file__).resolve().parent / "songs"
base.mkdir(exist_ok=True)
names = sorted(p.name for p in base.glob("*.osz"))
(base / "index.json").write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(names)}곡 등록:")
for n in names:
    print(" -", n)
input("\n엔터를 누르면 닫힙니다.")

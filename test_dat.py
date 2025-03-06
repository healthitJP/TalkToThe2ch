#!/usr/bin/env python3
import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from html import unescape  # &gt; など複数のエンティティをデコード

@dataclass
class DatEntry:
    """
    2chのdatファイル1行分を表すデータ構造。
    """
    name: str
    email: str
    date_time: str
    user_id: Optional[str]
    be_id: Optional[str]
    body: str
    title: Optional[str]
    # アンカー ">>数字" のリスト
    reply_targets: List[int] = field(default_factory=list)

def parse_date_id_be(date_id_be: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    日付とID、BEを切り分けて返す。
    例: "2023/10/10(火) 12:34:56 ID:abcdefgh12 BE:12345678"
         → date_time="2023/10/10(火) 12:34:56"
           user_id="abcdefgh12"
           be_id="12345678"
    """
    tmp = date_id_be
    user_id = None
    be_id = None

    # " ID:" が含まれるかどうか
    id_index = tmp.find(" ID:")
    if id_index != -1:
        date_part = tmp[:id_index].rstrip()
        tmp_rest = tmp[id_index + len(" ID:"):]
        be_index = tmp_rest.find(" BE:")
        if be_index != -1:
            user_id = tmp_rest[:be_index].strip()
            be_part = tmp_rest[be_index + len(" BE:"):]
            be_id = be_part.strip()
        else:
            user_id = tmp_rest.strip()
        return date_part.strip(), user_id, be_id
    else:
        # BEがあるかどうか
        be_index = tmp.find(" BE:")
        if be_index != -1:
            date_part = tmp[:be_index].rstrip()
            be_part = tmp[be_index + len(" BE:"):]
            be_id = be_part.strip()
            return date_part.strip(), user_id, be_id
        else:
            return date_id_be.strip(), None, None

def parse_body_and_extract_replies(raw_body: str) -> Tuple[str, List[int]]:
    """
    本文を整形し、“&gt;&gt;###”形式のアンカーを正規表現で拾って番号をリスト化する。
    
    1) <a ...>...</a> のようなタグがあれば中身だけ残しタグを除去
    2) 本文中にある &gt;&gt;(\d+) を探して reply_targets に追加
    3) HTMLエンティティ(例: &gt;)を通常文字列に戻す → ">>123" など
    4) <br> を改行(\n)に変換
    5) 各行の先頭・末尾の空白を除去
    """
    # (1) aタグを除去(本文内にある場合を想定)
    anchor_tag_pattern = re.compile(r"<a\b[^>]*>(.*?)</a>", flags=re.IGNORECASE | re.DOTALL)

    def anchor_replacer(match: re.Match) -> str:
        return match.group(1)  # タグ内テキストだけを返す

    without_a_tags = re.sub(anchor_tag_pattern, anchor_replacer, raw_body)

    # (2) &gt;&gt;(\d+) を探して抽出
    reply_targets = []
    anchor_matches = re.findall(r'&gt;&gt;(\d+)', without_a_tags)
    for match_id in anchor_matches:
        reply_targets.append(int(match_id))

    # (3) HTMLエンティティデコード → ">>123" の形に
    decoded = unescape(without_a_tags)

    # (4) <br> を改行に置き換える
    replaced = decoded.replace("<br>", "\n")

    # (5) 各行の前後スペースを除去
    lines = [line.strip() for line in replaced.split("\n")]
    clean_body = "\n".join(lines)

    return clean_body, reply_targets

def parse_dat_lines(lines: List[str]) -> List[DatEntry]:
    """
    datファイルの行(文字列リスト)を受け取り、DatEntryのリストを返す。
    """
    entries = []

    for i, line in enumerate(lines):
        # "<>"で構成されるフィールドを分割
        parts = line.split("<>")
        if len(parts) < 4:
            # 不正フォーマットの行はスキップやエラー処理
            continue

        name = parts[0]
        email = parts[1]
        date_id_be = parts[2]
        raw_body = parts[3]
        # 5番目があればタイトル、それ以外はNone
        title = parts[4] if len(parts) >= 5 else None

        # あぼーん特例 (必要に応じて細かい挙動を調整)
        if (name == "あぼーん" and email == "あぼーん"
                and date_id_be == "あぼーん" and raw_body == "あぼーん"):
            entries.append(DatEntry(
                name="あぼーん",
                email="あぼーん",
                date_time="あぼーん",
                user_id=None,
                be_id=None,
                body="",
                title=None if title == "あぼーん" else title
            ))
            continue

        date_time, user_id, be_id = parse_date_id_be(date_id_be)
        clean_body, reply_targets = parse_body_and_extract_replies(raw_body)

        entry = DatEntry(
            name=name,
            email=email,
            date_time=date_time,
            user_id=user_id,
            be_id=be_id,
            body=clean_body,
            title=title,
            reply_targets=reply_targets
        )
        entries.append(entry)

    return entries

def main():
    """
    datファイルを読み込み、DatEntryにパースし、結果を表示する簡易的な例。
    """
    dat_file_path = "example.dat"

    with open(dat_file_path, 'r', encoding='shift_jis', errors='replace') as f:
        lines = f.read().splitlines()

    entries = parse_dat_lines(lines)

    for idx, e in enumerate(entries, start=1):
        # 1番目の行ならスレッドタイトルを表示
        if idx == 1 and e.title:
            print(f"=== スレッドタイトル: {e.title} ===")

        print(f"[レス番号: {idx}]")
        print(f"  名前: {e.name}")
        print(f"  日付: {e.date_time}")
        if e.user_id:
            print(f"  ID: {e.user_id}")
        if e.be_id:
            print(f"  BE: {e.be_id}")
        # 本文が長い場合は先頭40文字だけ表示する例
        short_body = (e.body[:40] + '...') if len(e.body) > 40 else e.body
        print(f"  本文:\n{short_body}")
        if e.reply_targets:
            print(f"  → 返信先(レス番号): {e.reply_targets}")
        print()

if __name__ == "__main__":
    main()

from typing import TypedDict


class User(TypedDict):
    score: float
    rating: int
    atcoder_id: str
    solve_count: int
    notif_setting: bool


def make_users(data) -> dict[int, User]:
    "生のSQLデータからusersに対応するdictを返します。"
    ret = {}
    for i in data:
        ret[int(i[0])] = User(
            score=float(i[1]), rating=int(i[4]),
            atcoder_id=str(i[2]), solve_count=int(i[3]),
            notif_setting=bool(i[4])
        )
    return ret


def make_submissions(data) -> dict[str, dict[str, int]]:
    "生のSQLデータからsubmissionsに対応するdictを返します。"
    ret = {}
    for i in data:
        ret.setdefault(i[0], {})
        ret[i[0]][i[1]] = i[2]
    return ret

def make_diffdic(data) -> dict[str, int]:
    "生のSQLデータからdifficulty_dictionaryに対応するdictを返します。"
    ret = {}
    for i in data:
        ret[str(i[0])] = int(i[1])
    return ret

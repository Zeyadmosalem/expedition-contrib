"""Fetch and parse a GitHub contribution calendar (standard library only)."""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

GRAPHQL_URL = 'https://api.github.com/graphql'
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""
LEVELS = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2,
          'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}


@dataclass(frozen=True)
class Day:
    date: str
    count: int
    level: int      # 0 (none) .. 4 (busiest quartile)
    week: int       # column, 0 = oldest week
    weekday: int    # row, 0 = Sunday, like GitHub's calendar


@dataclass(frozen=True)
class Calendar:
    login: str
    total: int
    days: tuple[Day, ...]

    @property
    def weeks(self) -> int:
        return max((d.week for d in self.days), default=-1) + 1

    @property
    def active(self) -> list[Day]:
        return [d for d in self.days if d.count > 0]


def _level_from_count(count: int, cuts: list[int]) -> int:
    if count <= 0:
        return 0
    return 1 + sum(count > c for c in cuts)


def parse(payload: dict, login: str = '') -> Calendar:
    """Build a Calendar from a GraphQL response (or its `data` part)."""
    data = payload.get('data', payload)
    if payload.get('errors'):
        raise ValueError('GitHub API error: ' + '; '.join(e.get('message', '?') for e in payload['errors']))
    user = data.get('user')
    if user is None:
        raise ValueError(f'GitHub user {login!r} not found')
    cal = user['contributionsCollection']['contributionCalendar']
    raw = [(w, day) for w, week in enumerate(cal['weeks']) for day in week['contributionDays']]
    counts = sorted(d['contributionCount'] for _, d in raw if d['contributionCount'] > 0)
    cuts = [counts[len(counts) * q // 4] for q in (1, 2, 3)] if counts else []
    days = []
    for w, d in raw:
        count = int(d['contributionCount'])
        level = LEVELS.get(d.get('contributionLevel', ''), None)
        if level is None:
            level = _level_from_count(count, cuts)
        if count > 0:
            level = max(level, 1)          # every active day is a real block
        weekday = (dt.date.fromisoformat(d['date']).weekday() + 1) % 7
        days.append(Day(d['date'], count, level, w, weekday))
    return Calendar(login, int(cal.get('totalContributions', sum(d.count for d in days))), tuple(days))


def load(path: str, login: str = '') -> Calendar:
    with open(path, encoding='utf-8') as f:
        return parse(json.load(f), login)


def fetch(login: str, token: str, timeout: float = 30.0) -> dict:
    """Query the GraphQL API. The token only travels in the Authorization header."""
    if not token:
        raise ValueError('a GitHub token is required (set GITHUB_TOKEN)')
    body = json.dumps({'query': QUERY, 'variables': {'login': login}}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=body, method='POST', headers={
        'Authorization': f'bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'expedition-contrib',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'GitHub GraphQL request failed: HTTP {e.code}') from None

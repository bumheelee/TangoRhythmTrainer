#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tango_music_score.py
--------------------
탱고 음악 -> 음악 분석 데이터(JSON) -> 리듬게임 채보(OSZ)

핵심 구조
    audio
      ↓
    analyze_audio()
      ↓
    music_score.json
      ├─ tempo / beat / downbeat
      ├─ bars / beats
      ├─ musical events (onset, strength, spectral centroid, chroma)
      └─ phrase/section 정보
      ↓
    build_chart()
      ↓
    .osu
      ↓
    .osz

기존 tango_chart_gen.py와 달리 "분석 즉시 노트"로 만들지 않고,
중간에 편집 가능한 악보형 JSON을 남깁니다.

설치:
    pip install librosa soundfile numpy

예:
    python tango_music_score.py "Mi dolor.mp3"

    python tango_music_score.py "Mi dolor.mp3" --level 1
    python tango_music_score.py "Mi dolor.mp3" --level 2 --mode tango
    python tango_music_score.py "Mi dolor.mp3" --level 3 --mode salient

출력:
    ./charts/
      Mi dolor - music_score.json
      Mi dolor - Lv2.osz

주의:
    이 프로그램은 종이 악보를 복원하는 것이 아닙니다.
    녹음에서 "리듬/박자/음향 이벤트를 악보처럼 구조화"합니다.
    실제 멜로디 음표(MIDI/MusicXML)는 별도의 음원 분리/음정 추정 단계가
    필요하며, 탱고의 합주 음원에서는 자동 추정에 한계가 있습니다.
"""

import argparse
import json
import math
import os
import sys
import zipfile
from pathlib import Path

import librosa
import numpy as np


KEYS = 4
DEFAULT_SR = 22050
HOP = 512
OFFSET_MS = 0

# 음역 기반 레인
BANDS = [
    (30, 220),       # 0: bass
    (220, 900),      # 1: low-mid
    (900, 3000),     # 2: mid-high
    (3000, 9000),    # 3: high
]

LEVEL_CONFIG = {
    1: {"gap_ms": 330, "percentile": 65},
    2: {"gap_ms": 190, "percentile": 35},
    3: {"gap_ms": 110, "percentile": 10},
}


def norm(a):
    a = np.asarray(a, dtype=float)
    if len(a) == 0:
        return a
    lo, hi = np.min(a), np.max(a)
    if hi - lo < 1e-12:
        return np.zeros_like(a)
    return (a - lo) / (hi - lo)


def safe_float(x):
    return float(np.asarray(x).reshape(-1)[0])


def nearest_grid(t, grid, max_error):
    if len(grid) == 0:
        return float(t), False
    i = int(np.argmin(np.abs(grid - t)))
    if abs(float(grid[i]) - float(t)) <= max_error:
        return float(grid[i]), True
    return float(t), False


def detect_tempo_and_beats(y, sr, beats_per_bar=4):
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)

    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=HOP,
        start_bpm=100,
        tightness=120,
    )

    tempo = safe_float(tempo)
    beat_times = librosa.frames_to_time(
        beat_frames, sr=sr, hop_length=HOP
    )

    if len(beat_times) < 8:
        raise RuntimeError("박자를 충분히 찾지 못했습니다.")

    # beat_track이 곡 앞부분에서 놓친 박자를 평균 간격으로 보완
    interval = float(np.median(np.diff(beat_times)))
    lead = []
    t = float(beat_times[0] - interval)
    while t > 0.05:
        lead.append(t)
        t -= interval

    beat_times = np.array(sorted(lead) + list(beat_times), dtype=float)

    # downbeat 추정
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    bass = S[freqs < 250].sum(axis=0)
    bass = norm(bass)

    env = norm(onset_env)
    bf = np.clip(
        librosa.time_to_frames(
            beat_times, sr=sr, hop_length=HOP
        ),
        0,
        len(env) - 1,
    )

    strength = env[bf] + bass[
        np.clip(bf, 0, len(bass) - 1)
    ]

    phase_scores = np.array([
        strength[p::beats_per_bar].mean()
        for p in range(beats_per_bar)
    ])

    downbeat_phase = int(np.argmax(phase_scores))

    sorted_scores = np.sort(phase_scores)
    confidence = (
        float((sorted_scores[-1] - sorted_scores[-2]) /
              (sorted_scores[-1] + 1e-9))
        if len(sorted_scores) >= 2 else 0.0
    )

    return tempo, beat_times, downbeat_phase, confidence, onset_env


def make_grid(beat_times, subdivision=4):
    """
    각 beat를 subdivision개로 분할.
    subdivision=4이면 beat 사이를 4등분하여 16분음표 수준의
    시간 격자를 만듭니다.

    실제 채보에는 "소리가 있는 이벤트"만 사용하고,
    이 grid 자체는 악보의 시간축 기준으로 보존합니다.
    """
    if len(beat_times) < 2:
        return np.array([])

    grid = []
    for a, b in zip(beat_times[:-1], beat_times[1:]):
        step = (b - a) / subdivision
        for k in range(subdivision):
            grid.append(a + step * k)
    grid.append(float(beat_times[-1]))
    return np.asarray(grid, dtype=float)


def detect_downbeat_bars(
    beat_times,
    downbeat_phase,
    beats_per_bar=4,
):
    """
    beat index를 bar/beat position으로 변환.
    """
    rows = []
    for i, t in enumerate(beat_times):
        pos = (i - downbeat_phase) % beats_per_bar
        bar = (i - downbeat_phase) // beats_per_bar
        rows.append({
            "index": int(i),
            "time_ms": int(round(t * 1000)),
            "bar": int(max(0, bar)),
            "beat": int(pos + 1),
            "is_downbeat": bool(pos == 0),
        })
    return rows


def detect_events(y, sr, beat_times, subdivision=4):
    """
    음원에서 '악보 이벤트'를 추출합니다.

    각 이벤트:
      time_ms
      grid_time_ms
      snapped
      strength
      loudness
      spectral_centroid
      chroma
      pitch_class
    """
    onset_env = librosa.onset.onset_strength(
        y=y, sr=sr, hop_length=HOP
    )

    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=HOP,
        backtrack=False,
    )

    onset_times = librosa.frames_to_time(
        onset_frames, sr=sr, hop_length=HOP
    )

    rms = librosa.feature.rms(
        y=y, frame_length=2048, hop_length=HOP
    )[0]

    centroid = librosa.feature.spectral_centroid(
        y=y, sr=sr, hop_length=HOP
    )[0]

    chroma = librosa.feature.chroma_stft(
        y=y, sr=sr, hop_length=HOP
    )

    # onset_strength / feature 길이를 맞춤
    n = min(len(onset_env), len(rms), len(centroid), chroma.shape[1])
    onset_env = onset_env[:n]
    rms = rms[:n]
    centroid = centroid[:n]
    chroma = chroma[:, :n]

    grid = make_grid(beat_times, subdivision=subdivision)

    # onset의 너무 가까운 중복을 제거
    events = []
    min_gap = 0.045
    last_t = -999.0

    for frame, t in zip(onset_frames, onset_times):
        if frame >= n:
            continue

        t = float(t)

        if t - last_t < min_gap:
            continue

        grid_t, snapped = nearest_grid(
            t,
            grid,
            max_error=max(
                0.035,
                float(np.median(np.diff(beat_times))) * 0.12
            ),
        )

        c = chroma[:, frame]
        pitch_class = int(np.argmax(c))
        chroma_strength = float(np.max(c))

        events.append({
            "time_ms": int(round(t * 1000)),
            "grid_time_ms": int(round(grid_t * 1000)),
            "snapped": bool(snapped),
            "strength": round(float(onset_env[frame]), 4),
            "loudness": round(float(rms[frame]), 5),
            "spectral_centroid": round(float(centroid[frame]), 1),
            "pitch_class": pitch_class,
            "chroma_strength": round(chroma_strength, 4),
        })

        last_t = t

    # strength 정규화
    strengths = np.array([e["strength"] for e in events], dtype=float)
    loudness = np.array([e["loudness"] for e in events], dtype=float)

    s_norm = norm(strengths)
    l_norm = norm(loudness)

    for e, s, l in zip(events, s_norm, l_norm):
        e["strength_norm"] = round(float(s), 4)
        e["loudness_norm"] = round(float(l), 4)

    return events


def assign_musical_positions(events, bars, beats_per_bar=4):
    """
    각 event에 bar/beat/subdivision 위치를 붙입니다.
    """
    beat_times = np.array(
        [b["time_ms"] / 1000.0 for b in bars],
        dtype=float
    )

    for e in events:
        t = e["grid_time_ms"] / 1000.0

        if len(beat_times) == 0:
            continue

        idx = int(np.searchsorted(beat_times, t, side="right") - 1)
        idx = max(0, min(idx, len(beat_times) - 1))

        b = bars[idx]
        beat_start = beat_times[idx]

        if idx + 1 < len(beat_times):
            beat_len = beat_times[idx + 1] - beat_start
        elif idx > 0:
            beat_len = beat_start - beat_times[idx - 1]
        else:
            beat_len = 0.5

        fraction = 0.0 if beat_len <= 0 else (
            (t - beat_start) / beat_len
        )

        sub = int(round(fraction * 4))
        sub = max(0, min(3, sub))

        e["bar"] = int(b["bar"])
        e["beat"] = int(b["beat"])
        e["subdivision"] = int(sub)
        e["is_downbeat"] = bool(b["is_downbeat"] and sub == 0)

    return events


def detect_phrases(events, bars, beats_per_bar=4):
    """
    프레이즈 후보를 만듭니다.

    자동 프레이즈는 확정된 음악 형식 분석이 아니라,
    4마디 단위 + 긴 공백을 이용한 '편집 가능한 후보'입니다.
    """
    if not bars:
        return []

    max_bar = max(int(b["bar"]) for b in bars)
    boundaries = {0}

    # 기본 4마디 단위
    for bar in range(4, max_bar + 1, 4):
        boundaries.add(bar)

    # 긴 공백을 프레이즈 후보로 추가
    times = [e["grid_time_ms"] for e in events]
    for a, b in zip(times[:-1], times[1:]):
        if b - a >= 1200:
            # 다음 event의 bar
            candidates = [
                e["bar"] for e in events
                if e["grid_time_ms"] == b
            ]
            if candidates:
                boundaries.add(int(candidates[0]))

    boundaries = sorted(boundaries)
    phrases = []

    for i, start in enumerate(boundaries):
        end = (
            boundaries[i + 1] - 1
            if i + 1 < len(boundaries)
            else max_bar
        )
        phrases.append({
            "phrase": i + 1,
            "start_bar": int(start),
            "end_bar": int(end),
            "label": f"Phrase {i + 1}",
        })

    return phrases


def analyze_audio(
    path,
    beats_per_bar=4,
    subdivision=4,
    offset_ms=0,
):
    y, sr = librosa.load(
        path,
        sr=DEFAULT_SR,
        mono=True,
    )

    duration = len(y) / sr

    tempo, beat_times, downbeat_phase, confidence, _ = (
        detect_tempo_and_beats(
            y,
            sr,
            beats_per_bar=beats_per_bar,
        )
    )

    beat_times = beat_times + offset_ms / 1000.0

    bars = detect_downbeat_bars(
        beat_times,
        downbeat_phase,
        beats_per_bar=beats_per_bar,
    )

    events = detect_events(
        y,
        sr,
        beat_times,
        subdivision=subdivision,
    )

    # offset 적용
    if offset_ms:
        for e in events:
            e["time_ms"] += int(offset_ms)
            e["grid_time_ms"] += int(offset_ms)

    events = assign_musical_positions(
        events,
        bars,
        beats_per_bar=beats_per_bar,
    )

    phrases = detect_phrases(
        events,
        bars,
        beats_per_bar=beats_per_bar,
    )

    return {
        "schema": "tango-music-score-v1",
        "source": {
            "file": os.path.basename(path),
            "duration_sec": round(float(duration), 4),
            "sample_rate": int(sr),
        },
        "meter": {
            "beats_per_bar": int(beats_per_bar),
            "subdivision_per_beat": int(subdivision),
        },
        "tempo": {
            "bpm": round(float(tempo), 3),
            "beat_interval_ms": round(60000.0 / tempo, 3),
            "downbeat_phase": int(downbeat_phase),
            "downbeat_confidence": round(float(confidence), 4),
        },
        "bars": bars,
        "phrases": phrases,
        "events": events,
    }


def event_lane(e):
    """
    spectral centroid를 4개 레인으로 변환.
    """
    c = float(e.get("spectral_centroid", 1000))

    if c < 250:
        return 0
    if c < 900:
        return 1
    if c < 3000:
        return 2
    return 3


def add_note(notes, time_ms, lane, kind="event", accent=False):
    key = (int(time_ms), int(lane))
    if any(n["time_ms"] == key[0] and n["lane"] == key[1]
           for n in notes):
        return

    notes.append({
        "time_ms": int(max(0, time_ms)),
        "lane": int(max(0, min(KEYS - 1, lane))),
        "kind": kind,
        "accent": bool(accent),
    })


def build_tango_chart(score, level=2):
    """
    탱고 학습용 기본 채보.

    원칙:
      1. 다운비트는 동시 2키
      2. 실제 음악 이벤트가 있는 위치만 추가
      3. 이벤트의 음향 중심으로 레인 결정
      4. 레벨이 높아질수록 이벤트 밀도를 증가
    """
    events = score["events"]
    bars = score["bars"]
    cfg = LEVEL_CONFIG[level]

    notes = []

    # 1. 기본 beat skeleton
    for b in bars:
        if b["is_downbeat"]:
            add_note(
                notes,
                b["time_ms"],
                1,
                kind="downbeat",
                accent=True,
            )
            add_note(
                notes,
                b["time_ms"],
                2,
                kind="downbeat",
                accent=True,
            )
        elif level >= 2:
            lane = 0 if b["beat"] % 2 else 3
            add_note(
                notes,
                b["time_ms"],
                lane,
                kind="beat",
                accent=False,
            )

    # 2. 실제 음악 이벤트
    last_by_lane = [-999999] * KEYS

    for e in events:
        if level == 1:
            # Lv1은 downbeat + 강한 이벤트만
            if not e["is_downbeat"] and e["strength_norm"] < 0.75:
                continue
        elif level == 2:
            if e["strength_norm"] < 0.35:
                continue
        else:
            if e["strength_norm"] < 0.12:
                continue

        t = int(e["grid_time_ms"])
        lane = event_lane(e)

        # 같은 레인의 과밀 방지
        if t - last_by_lane[lane] < cfg["gap_ms"]:
            continue

        # 이미 beat skeleton이 있으면 중복 방지
        add_note(
            notes,
            t,
            lane,
            kind="musical_event",
            accent=bool(e["is_downbeat"]),
        )
        last_by_lane[lane] = t

    notes.sort(key=lambda x: (x["time_ms"], x["lane"]))

    return {
        "mode": "tango",
        "level": level,
        "notes": notes,
    }


def build_salient_chart(score, level=2):
    """
    잘 들리는 이벤트 중심 채보.
    기존 build_salient_notes의 개념을 score 기반으로 재구성.
    """
    events = score["events"]
    cfg = LEVEL_CONFIG[level]

    if not events:
        return {"mode": "salient", "level": level, "notes": []}

    strengths = np.array(
        [e["strength_norm"] for e in events],
        dtype=float,
    )

    threshold = float(np.percentile(
        strengths,
        cfg["percentile"]
    ))

    notes = []
    last_by_lane = [-999999] * KEYS

    for e in events:
        if e["strength_norm"] < threshold:
            continue

        lane = event_lane(e)
        t = int(e["grid_time_ms"])

        if t - last_by_lane[lane] < cfg["gap_ms"]:
            continue

        add_note(
            notes,
            t,
            lane,
            kind="salient",
            accent=bool(e["is_downbeat"]),
        )
        last_by_lane[lane] = t

    notes.sort(key=lambda x: (x["time_ms"], x["lane"]))

    return {
        "mode": "salient",
        "level": level,
        "notes": notes,
    }


def build_beat_chart(score, level=2):
    """
    기존 프로그램과 가장 비슷한 beat 기반 채보.
    """
    bars = score["bars"]
    notes = []

    for b in bars:
        if level == 1:
            if b["is_downbeat"]:
                add_note(notes, b["time_ms"], 1, "downbeat", True)
                add_note(notes, b["time_ms"], 2, "downbeat", True)
        else:
            if b["is_downbeat"]:
                add_note(notes, b["time_ms"], 1, "downbeat", True)
                add_note(notes, b["time_ms"], 2, "downbeat", True)
            else:
                lane = 0 if b["beat"] % 2 else 3
                add_note(notes, b["time_ms"], lane, "beat", False)

    # Lv3에서는 grid에 가까운 이벤트 추가
    if level >= 3:
        for e in score["events"]:
            if e["snapped"] and e["strength_norm"] >= 0.4:
                add_note(
                    notes,
                    e["grid_time_ms"],
                    event_lane(e),
                    "onset",
                    False,
                )

    notes.sort(key=lambda x: (x["time_ms"], x["lane"]))

    return {
        "mode": "beat",
        "level": level,
        "notes": notes,
    }


def build_instrument_chart(score, level=2):
    """
    음역/스펙트럼 중심 채보.
    """
    events = score["events"]
    cfg = LEVEL_CONFIG[level]

    notes = []
    last_by_lane = [-999999] * KEYS

    for e in events:
        if e["strength_norm"] < (0.2 if level >= 3 else 0.35):
            continue

        lane = event_lane(e)
        t = int(e["grid_time_ms"])

        if t - last_by_lane[lane] < cfg["gap_ms"]:
            continue

        add_note(
            notes,
            t,
            lane,
            "instrument",
            bool(e["is_downbeat"]),
        )
        last_by_lane[lane] = t

    notes.sort(key=lambda x: (x["time_ms"], x["lane"]))

    return {
        "mode": "instrument",
        "level": level,
        "notes": notes,
    }


def build_chart(score, mode="tango", level=2):
    if mode == "tango":
        return build_tango_chart(score, level)
    if mode == "beat":
        return build_beat_chart(score, level)
    if mode == "salient":
        return build_salient_chart(score, level)
    if mode == "instrument":
        return build_instrument_chart(score, level)
    raise ValueError(f"알 수 없는 mode: {mode}")


def write_json(score, chart, out_path):
    data = {
        "schema": score["schema"],
        "score": score,
        "chart": chart,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def write_csv(score, out_path):
    """
    사람이 Excel 등에서 확인할 수 있는 이벤트 목록.
    """
    import csv

    fields = [
        "bar",
        "beat",
        "subdivision",
        "time_ms",
        "grid_time_ms",
        "snapped",
        "strength_norm",
        "loudness_norm",
        "spectral_centroid",
        "pitch_class",
        "chroma_strength",
        "is_downbeat",
    ]

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()

        for e in score["events"]:
            w.writerow({
                k: e.get(k, "")
                for k in fields
            })


def to_key_layout(chart, keys=4):
    """
    내부 채보(4레인, lane 0~3)를 지정한 키 수(2 또는 4)로 변환.

    2키: 왼쪽 두 레인(0,1) -> 왼쪽(0), 오른쪽 두 레인(2,3) -> 오른쪽(1).
         다운비트(1,2 동시) -> 좌우 동시 노트가 됩니다.
         같은 레인에서 너무 가까운(80ms 미만) 일반 노트는 정리합니다.
    4키: 그대로.
    이미 변환된 채보(chart["keys"] == keys)는 그대로 반환합니다(중복 변환 방지).
    """
    keys = int(keys)
    if keys not in (2, 4):
        raise ValueError(f"keys는 2 또는 4만 지원합니다: {keys}")
    if chart.get("keys", 4) == keys:
        out = dict(chart)
        out["keys"] = keys
        return out

    # 현재 4키 -> 2키 변환만 지원
    prio = {"downbeat": 0, "beat": 1}
    src = sorted(
        chart["notes"],
        key=lambda n: (
            int(n["time_ms"]),
            0 if n.get("accent") else 1,
            prio.get(n.get("kind"), 2),
        ),
    )

    min_gap = 80
    last_t = {0: -10**9, 1: -10**9}
    seen = set()
    notes = []
    for n in src:
        lane = int(n["lane"]) >> 1
        t = int(n["time_ms"])
        if (t, lane) in seen:
            continue
        if not n.get("accent") and t - last_t[lane] < min_gap:
            continue
        seen.add((t, lane))
        last_t[lane] = t
        m = dict(n)
        m["lane"] = lane
        notes.append(m)

    notes.sort(key=lambda x: (x["time_ms"], x["lane"]))
    out = dict(chart)
    out["notes"] = notes
    out["keys"] = 2
    return out


def write_osz(
    audio_path,
    chart,
    score,
    out_path,
    pack="Tango",
    title=None,
    keys=None,
):
    """
    osu!mania 2K/4K .osz 생성. (keys 미지정 시 chart["keys"], 없으면 4)
    현재 사용 중인 HTML이 읽을 수 있는 구조를 유지합니다.
    """
    title = title or Path(audio_path).stem

    keys = int(keys or chart.get("keys", KEYS))
    chart = to_key_layout(chart, keys)

    bpm = float(score["tempo"]["bpm"])
    bars = score["bars"]

    first_beat_ms = (
        int(bars[0]["time_ms"])
        if bars else 0
    )

    beat_len = 60000.0 / bpm

    audio_ext = Path(audio_path).suffix.lower()
    audio_name = "audio" + audio_ext

    version = (
        f'{chart["mode"]}-Lv{chart["level"]}-{keys}K'
    )

    x_for = lambda lane: int(
        (lane + 0.5) * 512 / keys
    )

    lines = [
        "osu file format v14",
        "",
        "[General]",
        f"AudioFilename: {audio_name}",
        "AudioLeadIn: 0",
        "PreviewTime: -1",
        "Countdown: 0",
        "SampleSet: Normal",
        "Mode: 3",
        "",
        "[Metadata]",
        f"Title:{title}",
        f"TitleUnicode:{title}",
        "Artist:Tango",
        "ArtistUnicode:Tango",
        f"Creator:{pack}",
        f"Version:{version}",
        "Source:",
        f"Tags:tango {pack} music-score",
        "BeatmapID:0",
        "BeatmapSetID:-1",
        "",
        "[Difficulty]",
        "HPDrainRate:5",
        f"CircleSize:{keys}",
        "OverallDifficulty:5",
        "ApproachRate:5",
        "SliderMultiplier:1.4",
        "SliderTickRate:1",
        "",
        "[TimingPoints]",
        f"{first_beat_ms},{beat_len:.3f},4,1,0,60,1,0",
        "",
        "[HitObjects]",
    ]

    for n in chart["notes"]:
        lines.append(
            f'{x_for(n["lane"])},192,{n["time_ms"]},'
            f'1,0,0:0:0:0:'
        )

    osu_text = "\n".join(lines) + "\n"

    safe = "".join(
        c for c in title
        if c not in '\\/:*?"<>|'
    ).strip() or "song"

    out_path = Path(out_path)
    out_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(
        out_path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as z:
        z.writestr(
            f"{safe} [{version}].osu",
            osu_text,
        )
        z.write(
            audio_path,
            audio_name,
        )

    return str(out_path)


def process(path, args):
    path = os.path.abspath(path)
    title = Path(path).stem

    print(f"[1/4] 음악 분석: {title}")

    score = analyze_audio(
        path,
        beats_per_bar=args.beats,
        subdivision=args.subdivision,
        offset_ms=args.offset,
    )

    if args.downbeat is not None:
        # 사용자가 "첫 검출 beat가 실제 마디의 몇 번째인가"를 지정
        score["tempo"]["downbeat_phase"] = (
            -args.downbeat
        ) % args.beats

        phase = score["tempo"]["downbeat_phase"]

        beat_times = np.array([
            b["time_ms"] / 1000.0
            for b in score["bars"]
        ])

        score["bars"] = detect_downbeat_bars(
            beat_times,
            phase,
            args.beats,
        )

        score["events"] = assign_musical_positions(
            score["events"],
            score["bars"],
            args.beats,
        )

    print(
        f"      BPM={score['tempo']['bpm']:.2f}, "
        f"beat={len(score['bars'])}, "
        f"events={len(score['events'])}, "
        f"downbeat_conf={score['tempo']['downbeat_confidence']:.3f}"
    )

    print("[2/4] 악보형 JSON 생성")

    out_dir = Path(args.out)
    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    chart = build_chart(
        score,
        mode=args.mode,
        level=args.level,
    )
    chart = to_key_layout(chart, getattr(args, "keys", 2))

    json_path = (
        out_dir /
        f"{title} - music_score.json"
    )

    write_json(
        score,
        chart,
        json_path,
    )

    if args.csv:
        csv_path = (
            out_dir /
            f"{title} - events.csv"
        )
        write_csv(score, csv_path)
        print(f"      CSV: {csv_path}")

    print("[3/4] OSZ 생성")

    osz_path = (
        out_dir /
        f"{title} - {args.mode}-Lv{args.level}-{getattr(args, 'keys', 2)}K.osz"
    )

    write_osz(
        path,
        chart,
        score,
        osz_path,
        pack=args.pack,
        title=title,
    )

    print("[4/4] 완료")
    print(f"      SCORE: {json_path}")
    print(f"      OSZ  : {osz_path}")
    print(
        f"      NOTES: {len(chart['notes'])}"
    )

    return json_path, osz_path


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    ap.add_argument(
        "input",
        help="음악 파일 또는 폴더",
    )

    ap.add_argument(
        "--level",
        type=int,
        default=2,
        choices=[1, 2, 3],
        help="1=기초 / 2=표준 / 3=고밀도",
    )

    ap.add_argument(
        "--mode",
        choices=[
            "tango",
            "beat",
            "salient",
            "instrument",
        ],
        default="tango",
        help=(
            "tango=탱고 학습형 / "
            "beat=박자 중심 / "
            "salient=강한 음악 이벤트 / "
            "instrument=음역 중심"
        ),
    )

    ap.add_argument(
        "--beats",
        type=int,
        default=4,
        help="한 마디 박 수. 기본 4",
    )

    ap.add_argument(
        "--subdivision",
        type=int,
        default=4,
        choices=[2, 4, 8],
        help="박 1개를 몇 등분할지",
    )

    ap.add_argument(
        "--downbeat",
        type=int,
        default=None,
        help=(
            "첫 검출 beat가 실제 마디의 몇 번째 박인지 "
            "(0부터)"
        ),
    )

    ap.add_argument(
        "--offset",
        type=int,
        default=0,
        help="전체 타이밍 보정(ms)",
    )

    ap.add_argument(
        "--pack",
        default="Tango",
    )

    ap.add_argument(
        "--out",
        default="./charts",
    )

    ap.add_argument(
        "--keys",
        type=int,
        choices=[2, 4],
        default=2,
        help="채보 키 수 (2 또는 4, 기본 2)",
    )

    ap.add_argument(
        "--csv",
        action="store_true",
        help="악보 이벤트 CSV도 생성",
    )

    args = ap.parse_args()

    global OFFSET_MS
    OFFSET_MS = args.offset

    exts = (
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".m4a",
    )

    if os.path.isdir(args.input):
        files = sorted(
            os.path.join(args.input, f)
            for f in os.listdir(args.input)
            if f.lower().endswith(exts)
        )
    else:
        files = [args.input]

    if not files:
        sys.exit(
            "음악 파일을 찾지 못했습니다."
        )

    for f in files:
        try:
            process(f, args)
        except Exception as e:
            print(
                f"✘ {os.path.basename(f)}: {e}",
                file=sys.stderr,
            )




# ============================================================
# Advanced analysis / batch processing
# ============================================================

def estimate_key_and_chroma(score, y=None, sr=None):
    """
    Chroma 기반 조성 후보.
    실제 악보의 조성을 확정하는 기능이 아니라 후보를 제공한다.
    """
    if y is None or sr is None:
        return {
            "key": "Unknown",
            "mode": "unknown",
            "confidence": 0.0,
        }

    chroma = librosa.feature.chroma_cqt(
        y=y,
        sr=sr,
    )
    profile = np.mean(chroma, axis=1)

    # Krumhansl 계열의 간단한 major/minor profile
    major = np.array([
        6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
        2.52, 5.19, 2.39, 3.66, 2.29, 2.88
    ])
    minor = np.array([
        6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
        2.54, 4.75, 3.98, 2.69, 3.34, 3.17
    ])

    def corr(a, b):
        a = (a - np.mean(a)) / (np.std(a) + 1e-9)
        b = (b - np.mean(b)) / (np.std(b) + 1e-9)
        return float(np.dot(a, b) / len(a))

    names = [
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B"
    ]

    candidates = []

    for root in range(12):
        p = np.roll(major, root)
        candidates.append(
            (corr(profile, p), names[root], "major")
        )

        p = np.roll(minor, root)
        candidates.append(
            (corr(profile, p), names[root], "minor")
        )

    candidates.sort(reverse=True)
    best = candidates[0]
    second = candidates[1]

    confidence = max(
        0.0,
        min(
            1.0,
            (best[0] - second[0] + 0.1) / 0.3
        )
    )

    return {
        "key": best[1],
        "mode": best[2],
        "confidence": round(confidence, 4),
        "correlation": round(best[0], 4),
    }


def classify_event_role(event):
    """
    음향 특성으로 음악 이벤트의 '역할 후보'를 분류한다.

    이것은 실제 악기 분리 결과가 아니라 음향학적 휴리스틱이다.
    """
    c = float(event.get("spectral_centroid", 0))
    loud = float(event.get("loudness_norm", 0))
    strength = float(event.get("strength_norm", 0))

    if c < 250:
        role = "bass"
    elif c < 900:
        role = "rhythm_low"
    elif c < 3000:
        role = "melodic_mid"
    else:
        role = "melodic_high"

    if strength >= 0.80:
        accent = "accent"
    elif strength <= 0.20:
        accent = "weak"
    else:
        accent = "normal"

    event["role"] = role
    event["accent_class"] = accent
    event["musical_weight"] = round(
        0.55 * strength + 0.45 * loud,
        4
    )

    return event


def detect_phrase_features(score):
    """
    프레이즈별 밀도/강세/음역 변화를 계산한다.
    """
    phrases = score.get("phrases", [])
    events = score.get("events", [])

    for phrase in phrases:
        ev = [
            e for e in events
            if phrase["start_bar"] <= e.get("bar", -1)
            <= phrase["end_bar"]
        ]

        if not ev:
            phrase.update({
                "event_count": 0,
                "density": 0.0,
                "mean_strength": 0.0,
                "accent_count": 0,
                "dominant_role": "silence",
            })
            continue

        duration_bars = max(
            1,
            phrase["end_bar"] - phrase["start_bar"] + 1
        )

        roles = {}
        for e in ev:
            r = e.get("role", "unknown")
            roles[r] = roles.get(r, 0) + 1

        dominant = max(
            roles,
            key=roles.get
        )

        phrase.update({
            "event_count": len(ev),
            "density": round(
                len(ev) / duration_bars,
                3
            ),
            "mean_strength": round(
                float(np.mean([
                    e.get("strength_norm", 0)
                    for e in ev
                ])),
                4
            ),
            "accent_count": sum(
                e.get("accent_class") == "accent"
                for e in ev
            ),
            "dominant_role": dominant,
        })

    return phrases


def analyze_audio_advanced(
    path,
    beats_per_bar=4,
    subdivision=4,
    offset_ms=0,
):
    """
    기존 analyze_audio()를 확장한 버전.
    """
    y, sr = librosa.load(
        path,
        sr=DEFAULT_SR,
        mono=True,
    )

    duration = len(y) / sr

    tempo, beat_times, downbeat_phase, confidence, onset_env = (
        detect_tempo_and_beats(
            y,
            sr,
            beats_per_bar=beats_per_bar,
        )
    )

    beat_times = beat_times + offset_ms / 1000.0

    bars = detect_downbeat_bars(
        beat_times,
        downbeat_phase,
        beats_per_bar=beats_per_bar,
    )

    events = detect_events(
        y,
        sr,
        beat_times,
        subdivision=subdivision,
    )

    if offset_ms:
        for e in events:
            e["time_ms"] += int(offset_ms)
            e["grid_time_ms"] += int(offset_ms)

    events = assign_musical_positions(
        events,
        bars,
        beats_per_bar=beats_per_bar,
    )

    for e in events:
        classify_event_role(e)

    phrases = detect_phrases(
        events,
        bars,
        beats_per_bar=beats_per_bar,
    )

    score = {
        "schema": "tango-music-score-v2",
        "source": {
            "file": os.path.basename(path),
            "duration_sec": round(float(duration), 4),
            "sample_rate": int(sr),
        },
        "tempo": {
            "bpm": round(float(tempo), 3),
            "beat_interval_ms": round(
                60000.0 / tempo, 3
            ),
            "downbeat_phase": int(downbeat_phase),
            "downbeat_confidence": round(
                float(confidence),
                4,
            ),
        },
        "meter": {
            "beats_per_bar": int(beats_per_bar),
            "subdivision_per_beat": int(subdivision),
        },
        "analysis": {
            "type": "audio-derived-musical-score",
            "note": (
                "음원에서 추출한 리듬/음향 이벤트이며 "
                "원본 악보의 완전한 복원이 아님"
            ),
        },
        "bars": bars,
        "phrases": phrases,
        "events": events,
    }

    # 조성은 비용이 있으므로 옵션으로 계산
    score["harmony"] = estimate_key_and_chroma(
        score,
        y=y,
        sr=sr,
    )

    detect_phrase_features(score)

    return score


def build_midi_like_score(score):
    """
    MIDI/MusicXML로 발전시키기 위한 중간 구조.
    아직 실제 MIDI 파일을 생성하지 않고,
    pitch/time/duration/velocity의 공통 구조를 만든다.
    """
    notes = []

    events = score.get("events", [])

    for i, e in enumerate(events):
        t = int(e["grid_time_ms"])

        if i + 1 < len(events):
            next_t = int(events[i + 1]["grid_time_ms"])
            duration = max(50, min(1200, next_t - t))
        else:
            duration = 250

        # chroma pitch class를 기반으로 한 '대표 pitch 후보'
        pc = int(e.get("pitch_class", 0))

        # 실제 옥타브를 알 수 없으므로 MIDI 중심 음역을 가정
        role = e.get("role", "")
        if role == "bass":
            octave = 2
        elif role in ("rhythm_low", "melodic_mid"):
            octave = 4
        else:
            octave = 5

        midi_pitch = 12 * (octave + 1) + pc

        velocity = int(
            40 + 80 * float(
                e.get("musical_weight", 0)
            )
        )

        notes.append({
            "start_ms": t,
            "duration_ms": duration,
            "pitch": int(midi_pitch),
            "pitch_class": pc,
            "velocity": max(1, min(127, velocity)),
            "role": role,
            "bar": int(e.get("bar", 0)),
            "beat": int(e.get("beat", 1)),
            "subdivision": int(
                e.get("subdivision", 0)
            ),
        })

    return {
        "format": "midi-like-v1",
        "tempo_bpm": score["tempo"]["bpm"],
        "meter": score["meter"],
        "key": score["harmony"],
        "notes": notes,
    }


def build_musical_chart(score, level=2):
    """
    음악 역할을 최대한 보존하는 탱고 채보.

    Lv1: 다운비트/강세
    Lv2: 리듬 + 주요 멜로디
    Lv3: 프레이즈 내부의 세부 이벤트까지 반영
    """
    notes = []

    # beat skeleton
    for b in score["bars"]:
        if b["is_downbeat"]:
            add_note(
                notes,
                b["time_ms"],
                1,
                "downbeat",
                True,
            )
            add_note(
                notes,
                b["time_ms"],
                2,
                "downbeat",
                True,
            )
        elif level >= 2:
            # 2/4 느낌의 교대감을 살림
            lane = 0 if b["beat"] in (2, 4) else 3
            add_note(
                notes,
                b["time_ms"],
                lane,
                "beat",
                False,
            )

    # event selection
    gap = {
        1: 330,
        2: 170,
        3: 90,
    }[level]

    last_time = [-999999] * KEYS

    for e in score["events"]:
        strength = float(e.get("strength_norm", 0))
        role = e.get("role", "")
        accent = e.get("accent_class") == "accent"

        if level == 1:
            if not accent and not e.get("is_downbeat"):
                continue
        elif level == 2:
            if strength < 0.38:
                continue
        else:
            if strength < 0.10:
                continue

        # 역할에 따른 레인 배치
        if role == "bass":
            lane = 0
        elif role == "rhythm_low":
            lane = 1
        elif role == "melodic_mid":
            lane = 2
        else:
            lane = 3

        t = int(e["grid_time_ms"])

        if t - last_time[lane] < gap:
            continue

        add_note(
            notes,
            t,
            lane,
            role or "musical_event",
            bool(accent or e.get("is_downbeat")),
        )
        last_time[lane] = t

    notes.sort(
        key=lambda n: (
            n["time_ms"],
            n["lane"],
        )
    )

    return {
        "mode": "musical",
        "level": level,
        "notes": notes,
    }


def write_advanced_json(
    score,
    charts,
    midi_like,
    out_path,
):
    data = {
        "schema": "tango-music-score-v2",
        "score": score,
        "midi_like": midi_like,
        "charts": charts,
    }

    with open(
        out_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def process_advanced(
    path,
    args,
):
    """
    한 곡을 분석하고 여러 Lv / mode의 OSZ를 생성.
    """
    path = os.path.abspath(path)
    title = Path(path).stem

    out_dir = Path(args.out)
    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"\n▶ {os.path.basename(path)}"
    )

    score = analyze_audio_advanced(
        path,
        beats_per_bar=args.beats,
        subdivision=args.subdivision,
        offset_ms=args.offset,
    )

    print(
        "  BPM: "
        f"{score['tempo']['bpm']:.2f} | "
        "Events: "
        f"{len(score['events'])} | "
        "Key: "
        f"{score['harmony']['key']} "
        f"{score['harmony']['mode']}"
    )

    # 사용자가 downbeat를 지정한 경우 재정렬
    if args.downbeat is not None:
        phase = (-args.downbeat) % args.beats

        beat_times = np.array([
            b["time_ms"] / 1000.0
            for b in score["bars"]
        ])

        score["tempo"]["downbeat_phase"] = phase

        score["bars"] = detect_downbeat_bars(
            beat_times,
            phase,
            args.beats,
        )

        score["events"] = assign_musical_positions(
            score["events"],
            score["bars"],
            args.beats,
        )

    # MIDI-like
    midi_like = build_midi_like_score(score)

    # chart 목록
    charts = {}

    if args.all_levels:
        levels = [1, 2, 3]
    else:
        levels = [args.level]

    modes = (
        ["musical", "tango", "beat", "salient", "instrument"]
        if args.all_modes
        else [args.mode]
    )

    for mode in modes:
        for level in levels:
            if mode == "musical":
                chart = build_musical_chart(
                    score,
                    level,
                )
            else:
                chart = build_chart(
                    score,
                    mode=mode,
                    level=level,
                )

            chart = to_key_layout(chart, getattr(args, "keys", 2))

            key = f"{mode}-Lv{level}"
            charts[key] = chart

            osz_path = (
                out_dir /
                f"{title} - {key}-{getattr(args, 'keys', 2)}K.osz"
            )

            write_osz(
                path,
                chart,
                score,
                osz_path,
                pack=args.pack,
                title=title,
            )

            print(
                f"  ✓ {key} ({getattr(args, 'keys', 2)}키): "
                f"{len(chart['notes'])} notes"
            )

    json_path = (
        out_dir /
        f"{title} - music_score_v2.json"
    )

    write_advanced_json(
        score,
        charts,
        midi_like,
        json_path,
    )

    if args.csv:
        write_csv(
            score,
            out_dir /
            f"{title} - events.csv",
        )

    return json_path


def batch_process(
    input_dir,
    args,
):
    """
    특정 폴더의 모든 음원을 일괄 처리.
    하위 폴더도 선택적으로 검색.
    """
    input_dir = Path(input_dir)

    exts = {
        ".mp3",
        ".wav",
        ".flac",
        ".ogg",
        ".m4a",
        ".aac",
        ".wma",
    }

    if args.recursive:
        files = [
            p for p in input_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in exts
        ]
    else:
        files = [
            p for p in input_dir.iterdir()
            if p.is_file()
            and p.suffix.lower() in exts
        ]

    files.sort()

    if not files:
        print(
            f"음원 파일이 없습니다: {input_dir}"
        )
        return

    print(
        "\n"
        + "=" * 60
        + "\n"
        + "TANGO MUSIC BATCH PROCESSOR\n"
        + "=" * 60
    )
    print(
        f"입력 폴더 : {input_dir}"
    )
    print(
        f"음원 수   : {len(files)}"
    )
    print(
        f"출력 폴더 : {args.out}"
    )

    success = 0
    failed = 0

    for idx, path in enumerate(files, 1):
        print(
            f"\n[{idx}/{len(files)}]"
        )

        try:
            process_advanced(
                str(path),
                args,
            )
            success += 1
        except Exception as exc:
            failed += 1
            print(
                f"  ✗ 실패: {exc}",
                file=sys.stderr,
            )

    print(
        "\n"
        + "=" * 60
    )
    print(
        f"완료: {success}곡 / 실패: {failed}곡"
    )
    print(
        "=" * 60
    )


# ============================================================
# CLI override
# ============================================================

def advanced_main():
    ap = argparse.ArgumentParser(
        description=(
            "Tango Music Score Generator v2\n"
            "음원 -> 음악 분석 -> 악보형 JSON -> OSZ"
        )
    )

    ap.add_argument(
        "input",
        help=(
            "음원 파일 또는 음원이 들어 있는 폴더"
        ),
    )

    ap.add_argument(
        "--out",
        default="./charts",
        help="출력 폴더",
    )

    ap.add_argument(
        "--level",
        type=int,
        default=2,
        choices=[1, 2, 3],
    )

    ap.add_argument(
        "--mode",
        choices=[
            "musical",
            "tango",
            "beat",
            "salient",
            "instrument",
        ],
        default="musical",
    )

    ap.add_argument(
        "--all-levels",
        action="store_true",
        help="Lv1/Lv2/Lv3 모두 생성",
    )

    ap.add_argument(
        "--all-modes",
        action="store_true",
        help="모든 채보 모드 생성",
    )

    ap.add_argument(
        "--recursive",
        action="store_true",
        help="하위 폴더까지 검색",
    )

    ap.add_argument(
        "--beats",
        type=int,
        default=4,
        choices=[2, 3, 4],
    )

    ap.add_argument(
        "--subdivision",
        type=int,
        default=4,
        choices=[2, 4, 8],
    )

    ap.add_argument(
        "--downbeat",
        type=int,
        default=None,
        help="첫 검출 beat의 실제 박 번호(0부터)",
    )

    ap.add_argument(
        "--offset",
        type=int,
        default=0,
        help="전체 타이밍 보정(ms)",
    )

    ap.add_argument(
        "--pack",
        default="Tango",
    )

    ap.add_argument(
        "--keys",
        type=int,
        choices=[2, 4],
        default=2,
        help="채보 키 수 (2 또는 4, 기본 2)",
    )

    ap.add_argument(
        "--csv",
        action="store_true",
    )

    args = ap.parse_args()

    target = Path(args.input)

    if not target.exists():
        sys.exit(
            f"입력 경로가 없습니다: {target}"
        )

    if target.is_dir():
        batch_process(
            target,
            args,
        )
    else:
        process_advanced(
            str(target),
            args,
        )


if __name__ == "__main__":
    advanced_main()

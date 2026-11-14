"""オリジナル BGM 6曲を実楽器サンプル（GeneralUser GS）で録音する。大作映画風のオーケストラ。

中心の動機は「レ―ラ・ラー」（5度の跳躍）。試合では短調で勇ましく、勝利では長調で晴れやかに鳴る。
- menu      : 神秘的なタイトル曲（チェレスタ→弦とホルン）
- match     : 試合。低弦の16分の刻み、3+3+2 の太鼓、ホルン・トロンボーン・トランペットで主題
- tension   : 終盤（スニッチ出現後）。match を1音上げて速く
- story     : ストーリーの普段の会話。のどかで少しおどけた三拍子
- prebattle : ストーリーの試合前。鼓動と低弦の脈の上で主題が暗く迫る
- victory   : ストーリーの勝利後。主題を長調にした晴れやかな曲

必要なもの：Python（mido, numpy, scipy）、Node.js と spessasynth_core、FFmpeg、GeneralUser GS。
ゲームは録音済みの audio/*.ogg を読むだけで、このスクリプトは実行しない。

python tools/build-theme-music.py --soundfont GeneralUser-GS.sf2 --ffmpeg ffmpeg.exe [--synth-module spessasynth_core/dist/index.js] [--out audio]
"""
import argparse, json, random, subprocess, wave
from pathlib import Path

import mido
import numpy as np
from scipy.signal import fftconvolve

PPQ, RATE = 480, 44100
OFF = {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}


def pitch(name):
    acc = 1 if '#' in name else -1 if (len(name) > 2 and name[1] == 'b') else 0
    return OFF[name[0]] + acc + (int(name[-1]) + 1) * 12


def chord(name, octave):
    root = name[:2] if len(name) > 1 and name[1] in '#b' else name[:1]
    q = name[len(root):]
    iv = {'m':[0,3,7], '7':[0,4,7,10], 'm7':[0,3,7,10]}.get(q, [0,4,7])
    return [pitch(root + str(octave)) + i for i in iv]


def mel(s):
    out = []
    for bar in s.split('|'):
        at, evs = 0, []
        for tok in bar.split():
            n, l = tok.split(':'); l = int(l)
            if n != '-': evs.append((at, n, l))
            at += l
        out.append((evs, at))
    return out


class Score:
    def __init__(self, seed, transpose=0):
        self.ev = [[] for _ in range(16)]
        self.rng = random.Random(seed)
        self.tr = transpose

    def raw(self, ch, beat, msg):
        self.ev[ch].append((max(0, round(beat * PPQ)), msg))

    def setup(self, ch, program, vol, pan, rev=40):
        self.raw(ch, 0, mido.Message('program_change', channel=ch, program=program))
        for c, v in [(7, vol), (10, pan), (91, rev), (93, 0), (11, 110)]:
            self.raw(ch, 0, mido.Message('control_change', channel=ch, control=c, value=v))

    def expr(self, ch, beat, v):
        self.raw(ch, beat, mido.Message('control_change', channel=ch, control=11, value=max(1, min(127, round(v)))))

    def note(self, ch, n, beat, dur, vel, human=True):
        if ch != 9: n += self.tr
        if not 0 <= n <= 127: return
        if human:
            beat += self.rng.uniform(-0.006, 0.006)
            vel += self.rng.uniform(-4, 4)
        vel = max(1, min(127, round(vel)))
        self.raw(ch, beat, mido.Message('note_on', channel=ch, note=n, velocity=vel))
        self.raw(ch, beat + dur, mido.Message('note_off', channel=ch, note=n, velocity=0))

    def save(self, path, bpm, num, total_beats):
        mid = mido.MidiFile(ticks_per_beat=PPQ)
        cond = mido.MidiTrack()
        cond.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
        cond.append(mido.MetaMessage('time_signature', numerator=num, denominator=4, time=0))
        mid.tracks.append(cond)
        end = round(total_beats * PPQ)
        for evs in self.ev:
            if not evs: continue
            tr, prev = mido.MidiTrack(), 0
            for tick, msg in sorted(evs, key=lambda e: (e[0], e[1].type == 'note_on')):
                tr.append(msg.copy(time=tick - prev)); prev = tick
            tr.append(mido.MetaMessage('end_of_track', time=max(0, end - prev)))
            mid.tracks.append(tr)
        mid.save(path)


def near(n, lo):
    """n と同じ音名で lo 以上の最小の音"""
    while n < lo: n += 12
    while n - 12 >= lo: n -= 12
    return n


def play_line(s, ch, bar_mel, beat, unit, shift, vel, scale=.96, start=0.0, minlen=0.0):
    evs, _ = bar_mel
    for at, name, l in evs:
        s.note(ch, pitch(name) + shift, beat + at * unit + start, max(minlen, l * unit * scale), vel)


# =====================================================================
#  主題（すべてオリジナル）。中心となる動機は「レ―ラ・ラー」（5度の跳躍）。
#  試合では短調で勇ましく、勝利の場面では長調で晴れやかに鳴る。
# =====================================================================
EPIC_A = mel('D4:3 A4:1 A4:4 | Bb4:2 A4:1 G4:1 F4:4 | C5:3 F4:1 A4:4 | G4:6 E4:2 |'
             'D4:3 A4:1 D5:4 | F5:3 E5:1 D5:2 Bb4:2 | G4:2 Bb4:2 D5:2 G5:2 | E5:4 C#5:2 A4:2')
EPIC_B = mel('D5:3 F5:1 F5:4 | E5:2 F5:1 E5:1 C5:4 | E5:3 G5:1 G5:4 | F5:2 E5:1 D5:1 A4:4 |'
             'F5:3 Bb5:1 Bb5:4 | A5:2 G5:1 F5:1 C5:4 | D5:2 E5:2 F5:2 G5:2 | A5:4 G5:2 E5:2')
EPIC_F = mel('D4:3 A4:1 A4:4 | -:8 | D4:3 A4:1 A4:4 | -:8 | D4:3 A4:1 D5:4 | -:8 | G4:2 Bb4:2 D5:2 G5:2 | E5:4 C#5:2 A4:2')
CH_EA = ['Dm','Bb','F','C','Dm','Bb','Gm','A']
CH_EB = ['Bb','F','C','Dm','Bb','F','Gm','A']

PRE = mel('-:8 | -:8 | D4:3 A4:1 A4:4 | G4:2 F4:2 E4:4 | F4:3 D4:1 D4:4 | Bb4:4 A4:4 | A4:8 | -:8 |'
          'D5:3 A4:1 A4:4 | C5:2 Bb4:2 A4:4 | Bb4:3 G4:1 D5:4 | D5:2 C5:2 Bb4:4 | Eb5:3 Bb4:1 G4:4 | Bb4:4 G4:4 | A4:8 | C#5:4 E5:4')
CH_PRE = ['Dm','Dm','Dm','Dm','Bb','Bb','A','A','Dm','Dm','Gm','Gm','Eb','Eb','A','A']

VIC = mel('D5:3 A5:1 A5:4 | G5:2 F#5:2 E5:4 | D5:2 F#5:2 B5:4 | A5:2 G5:2 D5:4 | D5:3 A5:1 D6:4 | B5:2 A5:2 G5:4 | E5:2 A5:2 C#6:4 | D6:8 |'
          'B5:3 D6:1 D6:4 | A5:2 F#5:2 D5:4 | E5:2 G5:2 B5:4 | A5:4 G5:2 E5:2 | F#5:3 B5:1 B5:4 | G5:2 A5:2 B5:4 | A5:2 B5:2 C#6:4 | D6:8')
CH_VIC = ['D','A','Bm','G','D','G','A','D','G','D','Em','A','Bm','G','A','D']

TALK = mel('C5:1 F5:1 A5:2 G5:1 F5:1 | E5:2 G5:2 C5:2 | D5:1 F5:1 A5:2 G5:1 F5:1 | D5:3 Bb4:1 C5:1 D5:1 |'
           'C5:1 F5:1 A5:2 C6:2 | Bb5:2 A5:1 G5:1 D5:2 | E5:1 G5:1 Bb5:2 A5:1 G5:1 | F5:4 -:2 |'
           'D5:2 F5:2 Bb5:2 | A5:3 G5:1 F5:2 | G5:1 A5:1 Bb5:2 D5:2 | E5:4 C5:2 |'
           'F5:2 A5:2 D6:2 | Bb5:3 A5:1 G5:2 | G5:1 A5:1 Bb5:1 G5:1 E5:2 | F5:4 -:2')
CH_TALK = ['F','C','Dm','Bb','F','Gm','C7','F','Bb','F','Gm','C','Dm','Bb','C7','F']

for m, n in [(EPIC_A,8),(EPIC_B,8),(EPIC_F,8),(PRE,8),(VIC,8),(TALK,6)]:
    assert all(t == n for _, t in m), m


# ---------------- 試合曲（大作映画風のアクション） ----------------
def write_match(path, intense):
    bpm = 156 if intense else 140
    s = Score(20261114 + intense, transpose=2 if intense else 0)
    HORN, TBN, TPT, LOW, MID, VLN, BASS, TIMP, TAIKO, DR, CHOIR, BRS, TUBA, TREM, CEL = 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14
    s.setup(HORN, 60, 118, 54, 45); s.setup(TBN, 57, 100, 76, 40); s.setup(TPT, 56, 96, 70, 45)
    s.setup(LOW, 48, 108, 60, 25); s.setup(MID, 48, 84, 36, 30); s.setup(VLN, 48, 104, 44, 50)
    s.setup(BASS, 43, 104, 64, 25); s.setup(TIMP, 47, 110, 64, 35); s.setup(TAIKO, 116, 112, 64, 40)
    s.setup(DR, 0, 96, 64, 40); s.setup(CHOIR, 52, 82, 64, 70); s.setup(BRS, 61, 92, 84, 35)
    s.setup(TUBA, 58, 92, 70, 30); s.setup(TREM, 44, 72, 30, 60); s.setup(CEL, 8, 64, 90, 70)
    sections = [('S1', EPIC_A, CH_EA), ('S2', EPIC_A, CH_EA), ('S3', EPIC_B, CH_EB), ('S4', EPIC_F, CH_EA)]
    accents = {0, 3, 6, 8, 11, 14}            # 3+3+2 のうねり
    bar = 0
    for sec, theme, chords in sections:
        for i in range(8):
            beat, ch = bar * 4, chords[i]
            r3 = near(chord(ch, 2)[0], 45)     # 低弦の基音（A2〜G#3）
            tri4 = sorted(near(t, 60) for t in chord(ch, 4)[:3])
            e = {'S1': .82, 'S2': .95, 'S3': 1.0, 'S4': .7 + i * .045}[sec]
            if intense: e = min(1.06, e + .06)
            for c in (HORN, TBN, TPT, LOW, MID, VLN, CHOIR, BRS, TREM):
                s.expr(c, beat, 66 + e * 56)
            # 低弦の刻み（16分）：アクセントだけ5度・オクターブに跳ぶ
            for k in range(16):
                n = r3 + (12 if k in (6, 14) else 7 if k in (3, 11) else 0)
                v = (100 if k in accents else 64) * e
                s.note(LOW, n, beat + k / 4, .2, v)
            # 中音域の弦（8分）
            if sec != 'S1':
                for k in range(8):
                    s.note(MID, tri4[[0, 1, 2, 1, 0, 2, 1, 2][k]], beat + k / 2, .4, (78 if k % 3 == 0 else 60) * e)
            s.note(BASS, near(r3, 33), beat, 3.9, 96 * e)
            # 太鼓（3+3+2）
            for at in (0, 1.5, 3):
                if sec == 'S1' and at: continue
                s.note(TAIKO, 41 if at == 0 else 45, beat + at, .8, (112 if at == 0 else 92) * e)
                s.note(DR, 35, beat + at, .3, (100 if at == 0 else 80) * e, False)
            s.note(TIMP, near(r3, 40), beat, .9, 100 * e)
            if sec in ('S2', 'S3'): s.note(TIMP, near(r3 + 7, 40), beat + 2, .7, 84 * e)
            if intense or sec == 'S3':
                for k in range(16):
                    if k % 2: s.note(DR, 38, beat + k / 4, .05, (30 + (k % 4 == 3) * 18) * e)
            if i == 7:   # 次の場面への盛り上げ
                for k in range(16): s.note(DR, 38, beat + k / 4, .08, 40 + k * 4)
                for k in range(8): s.note(TIMP, near(r3, 40), beat + 2 + k / 4, .2, 60 + k * 7)
            if i == 0: s.note(DR, 49, beat, 2, 104 * e, False); s.note(DR, 57, beat + .02, 2, 80 * e, False)
            if sec == 'S3' and i % 2 == 0 and i: s.note(DR, 49, beat, 2, 84, False)
            # 合唱・トレモロ
            if sec != 'S1':
                for n in chord(ch, 4)[:3]: s.note(CHOIR, n, beat, 3.95, 70 * e)
            if sec in ('S3', 'S4'):
                for n in chord(ch, 5)[:3]: s.note(TREM, n, beat, 3.95, 58 * e)
            if sec in ('S2', 'S3'): s.note(TUBA, near(r3, 33) + 12, beat, 3.8, 84 * e)
            # 金管の刻み
            if sec == 'S3':
                for at, d in ((0, .6), (1.5, .4), (3, .8)):
                    for n in chord(ch, 3)[:3]: s.note(BRS, n, beat + at, d, 96 * e)
            # 主題
            if sec == 'S1':
                play_line(s, HORN, theme[i], beat, .5, 0, 104)
                play_line(s, TBN, theme[i], beat, .5, -12, 70)
            elif sec == 'S2':
                play_line(s, HORN, theme[i], beat, .5, 0, 112)
                play_line(s, TBN, theme[i], beat, .5, -12, 100)
                play_line(s, VLN, theme[i], beat, .5, 12, 84, 1.02)
            elif sec == 'S3':
                play_line(s, TPT, theme[i], beat, .5, 0, 104)
                play_line(s, VLN, theme[i], beat, .5, 12, 100, 1.02)
                play_line(s, HORN, theme[i], beat, .5, -12, 108)
                play_line(s, TBN, theme[i], beat, .5, -24, 86)
            else:
                play_line(s, HORN, theme[i], beat, .5, 0, 84 + i * 4)
                if i >= 6: play_line(s, VLN, theme[i], beat, .5, 12, 90, 1.02)
                for k in range(4): s.note(CEL, tri4[k % 3] + 24, beat + k + .5, .4, 44)
            bar += 1
    s.save(path, bpm, 4, bar * 4)
    return bar * 4 * 60 / bpm


# ---------------- メニュー曲（神秘的なタイトル曲） ----------------
def write_menu(path):
    bpm = 76
    s = Score(77)
    CEL, HARP, PAD, BASS, STR, HORN, CHOIR, TIMP, FL = 0,1,2,3,4,5,6,7,8
    s.setup(CEL, 8, 100, 52, 70); s.setup(HARP, 46, 92, 40, 60); s.setup(PAD, 49, 82, 70, 70)
    s.setup(BASS, 43, 90, 64, 50); s.setup(STR, 48, 100, 58, 65); s.setup(HORN, 60, 100, 76, 60)
    s.setup(CHOIR, 53, 72, 64, 80); s.setup(TIMP, 47, 80, 64, 50); s.setup(FL, 73, 80, 44, 70)
    for bar in range(16):
        beat, i = bar * 4, bar % 8
        ch, theme = CH_EA[i], EPIC_A[i]
        tones = sorted(near(t, 50) for t in chord(ch, 3)[:3])
        arp = tones + [t + 12 for t in tones] + [tones[0] + 24]
        for k, idx in enumerate([0, 1, 2, 3, 4, 5, 6, 5]):
            s.note(HARP, arp[idx], beat + k / 2, 1.4, 62 if k == 0 else 46)
        s.note(BASS, near(chord(ch, 2)[0], 33), beat, 3.9, 74)
        for n in chord(ch, 4)[:3]: s.note(PAD, n, beat, 3.95, 54 + (bar >= 8) * 10)
        if bar < 8:
            play_line(s, CEL, theme, beat, .5, 12, 86, 1.0, minlen=.9)
        else:
            play_line(s, STR, theme, beat, .5, 0, 92, 1.02)
            play_line(s, HORN, theme, beat, .5, -12, 70)
            play_line(s, FL, theme, beat, .5, 12, 50)
            for n in chord(ch, 4)[:3]: s.note(CHOIR, n, beat, 3.95, 52)
            s.note(CEL, arp[5] + 12, beat + 3, .5, 42)
        if bar == 15:
            for k in range(8): s.note(TIMP, 50, beat + 2 + k / 4, .2, 40 + k * 6)
    s.save(path, bpm, 4, 64)
    return 64 * 60 / bpm


# ---------------- ストーリー：普段の会話（のどかで少しおどけた学校の日常） ----------------
def write_story(path):
    bpm = 112
    s = Score(31)
    CL, BSN, PIZZ, CEL, FL, STR, HARP, GLK, OB = 0,1,2,3,4,5,6,7,8
    s.setup(CL, 71, 100, 50, 50); s.setup(BSN, 70, 96, 76, 45); s.setup(PIZZ, 45, 96, 64, 45)
    s.setup(CEL, 8, 80, 36, 60); s.setup(FL, 73, 98, 56, 55); s.setup(STR, 49, 70, 70, 60)
    s.setup(HARP, 46, 80, 40, 55); s.setup(GLK, 9, 56, 30, 60); s.setup(OB, 68, 84, 80, 50)
    bar = 0
    for p in range(2):
        for i in range(16):
            beat, ch = bar * 3, CH_TALK[i]
            r = near(chord(ch, 2)[0], 41)
            tri = chord(ch, 3)[:3]
            # ブン・チャッ・チャッ（ファゴットとピチカート）
            s.note(BSN, r if i % 2 == 0 else near(r + 7, 41), beat, .7, 82)
            for b in (1, 2):
                for n in tri: s.note(PIZZ, n + 12, beat + b, .25, 56)
            if p == 0:
                play_line(s, CL, TALK[i], beat, .5, 0, 90)
                if i % 4 == 3: s.note(CEL, tri[2] + 24, beat + 2.5, .4, 50)
            else:
                play_line(s, FL, TALK[i], beat, .5, 0, 88)
                play_line(s, GLK, TALK[i], beat, .5, 12, 36, .5)
                for n in chord(ch, 4)[:3]: s.note(STR, n, beat, 2.95, 50)
                s.note(OB, tri[1] + 12, beat + 1.5, 1.2, 50)     # 合いの手
            if i == 7 or i == 15:
                for k in range(6): s.note(HARP, tri[k % 3] + 12 * (1 + k // 3), beat + 1.5 + k / 4, .8, 50 + k * 3)
            bar += 1
    s.save(path, bpm, 3, bar * 3)
    return bar * 3 * 60 / bpm


# ---------------- ストーリー：試合前（大敵を前に、静かに燃えていく） ----------------
def write_prebattle(path):
    bpm = 100
    s = Score(55)
    LOW, BASS, HORN, TBN, TREM, CHOIR, TIMP, TAIKO, DR, PIZZ, TUBA = 0,1,2,3,4,5,6,7,9,8,10
    s.setup(LOW, 48, 104, 60, 30); s.setup(BASS, 43, 100, 64, 30); s.setup(HORN, 60, 112, 50, 55)
    s.setup(TBN, 57, 96, 78, 45); s.setup(TREM, 44, 74, 36, 65); s.setup(CHOIR, 53, 80, 64, 80)
    s.setup(TIMP, 47, 104, 64, 45); s.setup(TAIKO, 116, 108, 64, 50); s.setup(DR, 0, 90, 64, 45)
    s.setup(PIZZ, 45, 80, 30, 45); s.setup(TUBA, 58, 86, 70, 40)
    for bar in range(16):
        beat, ch = bar * 4, CH_PRE[bar]
        r3 = near(chord(ch, 2)[0], 38)
        e = .7 if bar < 8 else .9
        for c in (LOW, HORN, TBN, TREM, CHOIR): s.expr(c, beat, 66 + e * 56)
        # 低弦の8分の刻み（不安な脈）
        for k in range(8):
            s.note(LOW, r3 + (1 if (k == 7 and bar % 2) else 0), beat + k / 2, .35, (92 if k % 4 == 0 else 62) * e)
        s.note(BASS, near(r3, 28), beat, 3.9, 86 * e)
        # 心臓の鼓動
        s.note(DR, 35, beat, .3, 96 * e, False); s.note(DR, 35, beat + .4, .3, 70 * e, False)
        if bar % 2 == 0: s.note(TAIKO, 41, beat, 1, 96 * e)
        if bar >= 8:
            s.note(TAIKO, 45, beat + 2, .8, 80)
            for k in range(8): s.note(PIZZ, chord(ch, 5)[0] + (0 if k % 2 else 7), beat + k / 2, .15, 48)   # 時計の針
            for n in chord(ch, 5)[:3]: s.note(TREM, n, beat, 3.95, 60)
            s.note(TUBA, near(r3, 28) + 12, beat, 3.8, 80)
        if bar >= 4:
            for n in chord(ch, 4)[:3]: s.note(CHOIR, n, beat, 3.95, 56 + (bar >= 8) * 14)
        if bar in (6, 7, 14, 15):
            for k in range(16): s.note(TIMP, near(r3, 40), beat + k / 4, .2, 44 + (k + (bar % 2) * 16) * 2)
        play_line(s, HORN, PRE[bar], beat, .5, 0, 96 if bar < 8 else 110)
        if bar >= 8: play_line(s, TBN, PRE[bar], beat, .5, -12, 92)
    s.save(path, bpm, 4, 64)
    return 64 * 60 / bpm


# ---------------- ストーリー：試合後（勝利の達成感） ----------------
def write_victory(path):
    bpm = 88
    s = Score(99)
    HORN, TPT, STR, PAD, HARP, BASS, TIMP, DR, CHOIR, BELL, TBN, FL = 0,1,2,3,4,5,6,9,7,8,10,11
    s.setup(HORN, 60, 116, 52, 55); s.setup(TPT, 56, 100, 72, 55); s.setup(STR, 48, 108, 44, 60)
    s.setup(PAD, 49, 86, 70, 65); s.setup(HARP, 46, 90, 36, 60); s.setup(BASS, 43, 98, 64, 45)
    s.setup(TIMP, 47, 100, 64, 50); s.setup(DR, 0, 86, 64, 55); s.setup(CHOIR, 52, 82, 64, 80)
    s.setup(BELL, 14, 70, 80, 70); s.setup(TBN, 57, 92, 80, 50); s.setup(FL, 73, 76, 40, 60)
    for bar in range(16):
        beat, ch = bar * 4, CH_VIC[bar]
        big = bar >= 8
        tones = sorted(near(t, 50) for t in chord(ch, 3)[:3]); arp = tones + [t + 12 for t in tones]
        for k, idx in enumerate([0, 1, 2, 3, 4, 5, 4, 3]):
            s.note(HARP, arp[idx], beat + k / 2, 1.2, 54)
        for n in chord(ch, 4)[:3]: s.note(PAD, n, beat, 3.95, 64 + big * 8)
        s.note(BASS, near(chord(ch, 2)[0], 33), beat, 3.9, 88)
        s.note(TIMP, near(chord(ch, 2)[0], 40), beat, .9, 70 + big * 24)
        if big:
            s.note(TIMP, near(chord(ch, 2)[0] + 7, 40), beat + 2, .7, 72)
            for n in chord(ch, 4)[:3]: s.note(CHOIR, n, beat, 3.95, 72)
            for n in chord(ch, 3)[:3]: s.note(TBN, n, beat, 1.8, 74); s.note(TBN, n, beat + 2, 1.8, 66)
            play_line(s, TPT, VIC[bar], beat, .5, -12, 100)
            play_line(s, STR, VIC[bar], beat, .5, 0, 104, 1.02)
            play_line(s, HORN, VIC[bar], beat, .5, -12, 108)
            play_line(s, FL, VIC[bar], beat, .5, 12, 56)
        else:
            play_line(s, HORN, VIC[bar], beat, .5, -12, 104)
            if bar >= 4: play_line(s, STR, VIC[bar], beat, .5, 0, 80, 1.02)
        if bar in (8, 12): s.note(DR, 49, beat, 2, 96, False); s.note(BELL, chord(ch, 5)[0], beat, 2.5, 76)
        if bar == 0: s.note(DR, 49, beat, 2, 70, False)
        if bar in (7, 15):
            for k in range(12): s.note(HARP, arp[k % 6] + 12 * (k // 6), beat + 2 + k / 6, 1, 56 + k * 3)
            for k in range(8): s.note(TIMP, 50, beat + 2 + k / 4, .2, 50 + k * 6)
    s.save(path, bpm, 4, 64)
    return 64 * 60 / bpm

def render(args, mid, raw):
    cmd = ['node', 'tools/render-orchestra.mjs', args.soundfont, str(mid), str(raw)]
    if args.synth_module: cmd.append(args.synth_module)
    subprocess.run(cmd, check=True)


def master(args, raw, seconds, out_wav, peak, room):
    pcm = subprocess.run([args.ffmpeg, '-v', 'error', '-nostdin', '-i', str(raw), '-f', 'f32le', '-ac', '2', '-ar', str(RATE), 'pipe:1'],
                         capture_output=True, check=True)
    data = np.frombuffer(pcm.stdout, dtype='<f4').reshape(-1, 2).copy()
    # ホールの響きを録音に焼き込む（ゲーム中に残響処理はしない）
    rng = np.random.default_rng(20261114)
    dry = data.copy()
    t = np.arange(round(RATE * 2.6)) / RATE
    for c in range(2):
        ir = rng.normal(size=len(t)) * np.exp(-t * 3.0)
        ir *= room / np.sqrt(np.sum(ir ** 2))
        ir[:round(RATE * .02)] = 0
        data[:, c] += fftconvolve(dry[:, 1 - c] * .5 + dry[:, c] * .5, ir)[:len(data)]
    frames = round(seconds * RATE)
    tail = data[frames:frames + 4 * RATE]
    loop = data[:frames].copy()
    loop[:len(tail)] += tail  # 曲尾の残響を頭に重ねてつなぎ目なくループ
    loop = np.tanh(loop * 1.1)
    loop *= peak / max(1e-3, float(np.max(np.abs(loop))))
    n = round(RATE * .006); w = (1 - np.arange(n) / n) ** 2
    for c in range(2):
        a, b = loop[0, c], loop[-1, c]; j = (a + b) / 2
        loop[:n, c] += (j - a) * w; loop[-n:, c] += (j - b) * w[::-1]
    with wave.open(str(out_wav), 'wb') as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(RATE)
        f.writeframes((np.clip(loop, -1, 1) * 32767).astype('<i2').tobytes())
    return loop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--synth-module'); ap.add_argument('--soundfont', required=True); ap.add_argument('--ffmpeg', required=True)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--out', default='audio')
    args = ap.parse_args()
    work = Path('output/audio/theme-v5'); work.mkdir(parents=True, exist_ok=True)
    jobs = [('menu', write_menu, .6, .16), ('match', lambda p: write_match(p, False), .86, .18), ('tension', lambda p: write_match(p, True), .86, .18),
            ('story', write_story, .55, .14), ('prebattle', write_prebattle, .78, .2), ('victory', write_victory, .8, .2)]
    rep = []
    for key, fn, peak, room in jobs:
        if args.only and key not in args.only: continue
        mid = work / (key + '.mid'); seconds = fn(mid)
        render(args, mid, work / (key + '-raw.wav'))
        loop = master(args, work / (key + '-raw.wav'), seconds, work / (key + '.wav'), peak, room)
        dest = Path(args.out) / (key + '.ogg')
        subprocess.run([args.ffmpeg, '-v', 'error', '-nostdin', '-y', '-i', str(work / (key + '.wav')), '-c:a', 'libvorbis', '-q:a', '5', str(dest)], check=True)
        rep.append({'key': key, 'seconds': round(seconds, 2), 'rms': round(float(np.sqrt(np.mean(loop ** 2))), 3), 'bytes': dest.stat().st_size})
    print(json.dumps(rep, indent=2))


if __name__ == '__main__':
    main()

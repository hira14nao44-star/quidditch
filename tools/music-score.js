// Original menu/stinger score and offline master renderer.
// Development only. The game loads the pre-rendered Ogg files in audio/.
// Action cues use tools/build-match-music.py with real instrument samples.
// Load in a browser; await renderQuidditchMusic('menu'|'fx:goal'|...).
(()=>{
let seed = 1;
function musicRandom(){ seed = (Math.imul(seed,1664525)+1013904223)>>>0; return seed/4294967296; }
const NOTE_I = {C:0,D:2,E:4,F:5,G:7,A:9,B:11};
function nf(n){ const m = /^([A-G])([#b]?)(-?\d)$/.exec(n); const k = NOTE_I[m[1]] + (m[2]==='#'?1:m[2]==='b'?-1:0) + (+m[3]+1)*12; return 440*Math.pow(2,(k-69)/12); }
function chordF(name, oct){
  const m = /^([A-G][b#]?)(.*)$/.exec(name), r = nf(m[1]+oct), q = m[2];
  const iv = q==='m' ? [0,3,7] : q==='7' ? [0,4,7,10] : q==='maj7' ? [0,4,7,11] : q==='dim' ? [0,3,6] : q==='m6' ? [0,3,7,9] : q==='m7b5' ? [0,3,6,10] : q==='sus' ? [0,5,7] : [0,4,7];
  return iv.map(i=>r*Math.pow(2,i/12));
}
function melody(str){ // "D5:2 F5:2 | ..." → 小節ごとの [{s,f,l}]
  return str.split('|').map(b=>{ let s = 0; return b.trim().split(/\s+/).filter(Boolean).map(tok=>{ const [n,l] = tok.split(':'); const ev = n==='-' ? null : {s, f:nf(n), l:+l}; s += +l; return ev; }).filter(Boolean); });
}
const SONGS = {
  // メニュー：灯りの向こう（3/4・Eマイナー）。後半は木管の応答を重ねる。
  menu: { spb:6, bpm:96, div:2, passes:2,
    chords:['Em','Cmaj7','Am6','B7','Em','G','D','F#dim','Cmaj7','Am','Em','B7','Am','F#dim','B7','Em'],
    mel: melody(`E5:1 G5:1 F#5:2 B5:1 A5:1 | G5:3 E5:1 D5:2 | C5:2 E5:1 A5:1 B5:2 | F#5:3 D#5:1 B4:2 |
                 E5:2 B5:1 A5:1 G5:2 | D6:2 B5:2 G5:2 | A5:3 F#5:1 E5:2 | C6:2 A5:1 F#5:1 A5:2 |
                 G5:1 E5:1 B5:2 G5:2 | A5:2 E5:1 C5:1 E5:2 | B4:1 E5:1 G5:2 F#5:2 | D#5:3 F#5:1 B5:2 |
                 C6:2 B5:1 A5:1 E5:2 | A5:1 F#5:1 C5:2 D#5:2 | F#5:2 D#5:1 B4:1 F#5:2 | E5:4 -:2`) },
  // 試合：風を追う翼（4/4・Dマイナー）
  match: { spb:16, bpm:124, div:4, passes:1,
    chords:['Dm','Bb','F','C','Dm','Bb','Gm','A','Gm','Bb','F','C','Gm','Bb','A7','A'],
    mel: melody(`D4:4 F4:2 A4:2 E5:4 D5:4 | F5:6 D5:2 Bb4:8 | A4:4 C5:4 F5:6 E5:2 | D5:4 G4:4 E4:8 |
                 A4:2 D5:2 F5:4 E5:4 D5:4 | Bb4:4 F5:4 D5:8 | G4:4 D5:2 Bb4:2 G5:8 | E5:6 C#5:2 A4:8 |
                 D5:4 G5:4 F5:4 D5:4 | Bb5:6 A5:2 F5:8 | C6:4 A5:4 F5:4 E5:4 | G5:8 E5:8 |
                 D5:2 G5:2 Bb5:4 A5:4 G5:4 | F5:6 D5:2 Bb4:8 | E5:4 G5:4 C#5:6 E5:2 | A4:8 C#5:4 -:4`) },
};

function irBuf(a, sec){
  const n = Math.floor(a.sampleRate*sec), b = a.createBuffer(2, n, a.sampleRate);
  for (let c=0;c<2;c++){ const d = b.getChannelData(c); for (let i=0;i<n;i++){ const x = i/n; d[i] = (musicRandom()*2-1)*Math.pow(1-x, 3.2)*(i < a.sampleRate*0.012 ? 0.3 : 1); } }
  return b;
}
function createMusicInstruments(a){
  const dry = a.createGain(), wet = a.createGain(), conv = a.createConvolver();
  dry.gain.value = 0.8; dry.connect(a.destination);
  wet.gain.value = 0.38; conv.buffer = irBuf(a, 2.6); wet.connect(conv); conv.connect(a.destination);
  const noiseBuf = a.createBuffer(1, a.sampleRate*2, a.sampleRate), nd = noiseBuf.getChannelData(0);
  for (let i=0;i<nd.length;i++) nd[i] = musicRandom()*2-1;
  const waves = {};
  for (const [name, partials] of Object.entries({bow:[0,1,.32,.22,.12,.08,.05,.025], reed:[0,1,.12,.3,.035,.07], mellow:[0,1,.5,.25,.12,.06]})){
    waves[name] = a.createPeriodicWave(new Float32Array(partials.length), new Float32Array(partials));
  }
  function mVoice(send){ const g = a.createGain(); g.connect(dry); if (send){ const s = a.createGain(); s.gain.value = send; g.connect(s); s.connect(wet); } return g; }
  function mOsc(type, f, t, end, dest, det=0, gain=1){
    const o = a.createOscillator(); if (waves[type]) o.setPeriodicWave(waves[type]); else o.type = type; o.frequency.setValueAtTime(f, t); if (det) o.detune.value = det;
    if (gain !== 1){ const g = a.createGain(); g.gain.value = gain; o.connect(g); g.connect(dest); } else o.connect(dest);
    o.start(t); o.stop(end); return o;
  }
  const INS = {
    celesta(t, f, v){
      const g = mVoice(0.7); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.004); g.gain.exponentialRampToValueAtTime(0.0008, t+1.5);
      mOsc('sine', f, t, t+1.55, g); mOsc('sine', f*2.002, t, t+1.55, g, 0, 0.16);
      const h = a.createGain(); h.connect(g); h.gain.setValueAtTime(0.35, t); h.gain.exponentialRampToValueAtTime(0.001, t+0.22); mOsc('sine', f*4, t, t+0.25, h);
    },
    bell(t, f, v){
      const g = mVoice(0.85); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.003); g.gain.exponentialRampToValueAtTime(0.0006, t+2.2);
      mOsc('sine', f, t, t+2.25, g); mOsc('sine', f*2, t, t+1.2, g, 0, 0.18);
      const h = a.createGain(); h.connect(g); h.gain.setValueAtTime(0.4, t); h.gain.exponentialRampToValueAtTime(0.001, t+0.35); mOsc('sine', f*2.76, t, t+0.4, h); mOsc('sine', f*5.4, t, t+0.2, h, 0, 0.25);
    },
    trem(t, f, d, v){
      const g = mVoice(0.7), am = a.createGain(); am.connect(g);
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+Math.min(0.6, d*0.4)); g.gain.setValueAtTime(v, t+d); g.gain.linearRampToValueAtTime(0, t+d+0.8);
      const lfo = a.createOscillator(), lg = a.createGain(); lfo.frequency.value = 9.5; lg.gain.value = 0.45; lfo.connect(lg); lg.connect(am.gain); am.gain.value = 0.55;
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2400; lp.connect(am);
      [-6, 6].forEach(dt=>mOsc('bow', f, t, t+d+0.85, lp, dt, 0.6)); lfo.start(t); lfo.stop(t+d+0.85);
    },
    horn(t, f, d, v){
      const g = mVoice(0.6); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.18); g.gain.setValueAtTime(v, t+d); g.gain.linearRampToValueAtTime(0, t+d+0.5);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(500, t); lp.frequency.linearRampToValueAtTime(1300, t+0.25); lp.connect(g);
      mOsc('mellow', f, t, t+d+0.55, lp, -3, 0.6); mOsc('triangle', f, t, t+d+0.55, lp, 4, 1.25);
    },
    woodwind(t, f, d, v){
      const g = mVoice(0.55); g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(v, t+Math.min(0.07,d*0.25));
      g.gain.setValueAtTime(v*0.85, t+d); g.gain.linearRampToValueAtTime(0, t+d+0.16);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = Math.min(5000,f*5); lp.connect(g);
      const o = mOsc('reed', f, t, t+d+0.2, lp), lfo = a.createOscillator(), depth = a.createGain();
      lfo.frequency.value = 4.7; depth.gain.setValueAtTime(0,t); depth.gain.linearRampToValueAtTime(f*0.002,t+Math.min(0.3,d));
      lfo.connect(depth); depth.connect(o.frequency); lfo.start(t); lfo.stop(t+d+0.2);
    },
    harp(t, f, v){
      const g = mVoice(0.45); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.003); g.gain.exponentialRampToValueAtTime(0.0008, t+1.8);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.setValueAtTime(Math.min(9000, f*8), t); lp.frequency.exponentialRampToValueAtTime(Math.max(300, f*1.5), t+0.6); lp.connect(g);
      mOsc('triangle', f, t, t+1.85, lp); mOsc('sine', f*2, t, t+1.85, lp, 0, 0.3);
    },
    pad(t, f, d, v){
      const g = mVoice(0.6); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+Math.min(0.5, d*0.4)); g.gain.setValueAtTime(v, t+d); g.gain.linearRampToValueAtTime(0, t+d+0.6);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 1500; lp.Q.value = 0.3; lp.connect(g);
      mOsc('bow', f, t, t+d+0.65, lp, -7); mOsc('bow', f, t, t+d+0.65, lp, 7);
    },
    stac(t, f, v){
      const g = mVoice(0.22); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.008); g.gain.exponentialRampToValueAtTime(0.0008, t+0.17);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2300; lp.connect(g);
      mOsc('bow', f, t, t+0.19, lp, 0, 1.4);
    },
    bass(t, f, d, v){
      const g = mVoice(0.1); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.012); g.gain.setTargetAtTime(v*0.55, t+0.05, 0.12); g.gain.setTargetAtTime(0, t+d, 0.05);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 520; lp.connect(g);
      mOsc('bow', f, t, t+d+0.3, lp); mOsc('sine', f, t, t+d+0.3, g, 0, 0.6);
    },
    brass(t, f, d, v){
      const g = mVoice(0.4); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.035); g.gain.setTargetAtTime(v*0.75, t+0.08, 0.2); g.gain.setTargetAtTime(0, t+d, 0.07);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 1.2;
      lp.frequency.setValueAtTime(450, t); lp.frequency.exponentialRampToValueAtTime(2800, t+0.06); lp.frequency.exponentialRampToValueAtTime(1600, t+0.3); lp.connect(g);
      // ゆるいビブラート
      const lfo = a.createOscillator(), lg = a.createGain(); lfo.frequency.value = 5.2; lg.gain.setValueAtTime(0, t); lg.gain.linearRampToValueAtTime(f*0.006, t+Math.min(0.5, d)); lfo.connect(lg);
      const o1 = mOsc('bow', f, t, t+d+0.4, lp, -4), o2 = mOsc('bow', f, t, t+d+0.4, lp, 5);
      lg.connect(o1.frequency); lg.connect(o2.frequency); lfo.start(t); lfo.stop(t+d+0.4);
    },
    strings(t, f, d, v){
      const g = mVoice(0.55); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.07); g.gain.setValueAtTime(v, t+d); g.gain.setTargetAtTime(0, t+d, 0.1);
      const lp = a.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 3200; lp.connect(g);
      const lfo = a.createOscillator(), lg = a.createGain(); lfo.frequency.value = 5.6; lg.gain.value = f*0.005; lfo.connect(lg);
      const os = [-8, 8].map(dt=>mOsc('bow', f, t, t+d+0.5, lp, dt, 0.75)); os.forEach(o=>lg.connect(o.frequency)); lfo.start(t); lfo.stop(t+d+0.5);
    },
    timp(t, f, v){
      const g = mVoice(0.35); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t+0.006); g.gain.exponentialRampToValueAtTime(0.001, t+1.1);
      const o = a.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(f*1.5, t); o.frequency.exponentialRampToValueAtTime(f, t+0.06); o.connect(g); o.start(t); o.stop(t+1.15);
      mOsc('sine', f*1.51, t, t+0.5, g, 0, 0.25);
      const s = a.createBufferSource(), lp = a.createBiquadFilter(), ng = a.createGain(); s.buffer = noiseBuf; lp.type = 'lowpass'; lp.frequency.value = 260;
      ng.gain.setValueAtTime(v*1.4, t); ng.gain.exponentialRampToValueAtTime(0.001, t+0.18); s.connect(lp); lp.connect(ng); ng.connect(g); s.start(t); s.stop(t+0.2);
    },
    tick(t, v, hp=7000, d=0.06){
      const g = mVoice(0.15), s = a.createBufferSource(), f = a.createBiquadFilter(); s.buffer = noiseBuf; f.type = 'highpass'; f.frequency.value = hp;
      g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t+d); s.connect(f); f.connect(g); s.start(t, musicRandom()); s.stop(t+d+0.02);
    },
    swell(t, d, v){
      const g = mVoice(0.5), s = a.createBufferSource(), f = a.createBiquadFilter(); s.buffer = noiseBuf; s.loop = true; f.type = 'highpass'; f.frequency.value = 4500;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t+d); g.gain.exponentialRampToValueAtTime(0.0005, t+d+1.2); s.connect(f); f.connect(g); s.start(t); s.stop(t+d+1.3);
    },
  };

  // --- 1ステップ分を鳴らす ---
  return INS;
}

function playStep(INS, name, bar, s, t, sl, intense=false){
  const S = SONGS[name], b = bar % S.chords.length, ch = S.chords[b], pass = Math.floor(bar / S.chords.length);
  if (name==='menu'){
    const bar6 = sl*6;
    // ハープとチェレスタの間に余白を残し、後半で木管が旋律を受け取る。
    const arp = chordF(ch,3).slice(0,3).concat(chordF(ch,4).slice(0,3));
    if ([0,2,3,5].includes(s)) INS.harp(t, arp[s % arp.length] * (s===0 ? 0.5 : 1), s===0 ? 0.075 : 0.032);
    if (s===0){
      chordF(ch,4).slice(0,3).forEach(f=>INS.pad(t, f, bar6*0.88, 0.009));
      INS.bass(t, chordF(ch,2)[0], bar6*0.7, 0.035);
      if (b % 4 === 0) INS.horn(t, chordF(ch,3)[0], bar6*1.4, 0.022);
    }
    for (const ev of S.mel[b]) if (ev.s===s){
      if (pass===1 && b%8>=4) INS.woodwind(t, ev.f/2, ev.l*sl*0.88, 0.085);
      else INS.celesta(t, ev.f, 0.105);
      if (pass===1 && ev.s===0) INS.celesta(t, ev.f*2, 0.023);
    }
    if ((b===3 || b===11) && s===4) INS.bell(t, chordF(ch,5)[2], 0.025);
    if (b===15 && s===4) for (let k=0;k<6;k++) INS.harp(t+k*sl/3, chordF('Em',4+Math.floor(k/3))[k%3], 0.028);
    return;
  }
  // match
  const I = intense, tri = chordF(ch,3);
  const pat = [0,0,2,0][s%4], oct = (s%8===6) ? 2 : 1;
  if (s%2===0 || I) INS.stac(t, tri[pat]*oct, s%4===0 ? 0.038 : 0.023);
  if (s%4===0) INS.bass(t, chordF(ch,2)[0], sl*3, 0.12);
  if (s===0) chordF(ch,4).slice(0,3).forEach(f=>INS.pad(t, f, sl*16, 0.011));
  if (s===0) INS.timp(t, chordF(ch,2)[0], 0.42);
  if (s===8) INS.timp(t, chordF(ch,2)[2] || chordF(ch,2)[0], 0.28);
  if (I && (s===4 || s===12)) INS.timp(t, chordF(ch,2)[0], 0.22);
  if ((b===7 || b===15) && s>=12) INS.timp(t, chordF(ch,2)[0]*(s===15?1.5:1), 0.18 + (s-12)*0.04);
  if (I && s%2===0) INS.tick(t, s%4===0 ? 0.05 : 0.025);
  if (I && s%2===1){ const cf = chordF(ch,5), k = [0,1,2,1][(s>>1)%4]; INS.celesta(t, cf[k]*(s%8===7?2:1), 0.03); }
  for (const ev of S.mel[b]) if (ev.s===s){
    if (b < 8){ INS.horn(t, ev.f, ev.l*sl*0.95, 0.07); if (I) INS.brass(t, ev.f, ev.l*sl*0.95, 0.04); }
    else INS.strings(t, ev.f, ev.l*sl*0.95, 0.05);
    if (b >= 8 && I) INS.brass(t, ev.f/2, ev.l*sl*0.95, 0.04);
  }
}

// --- 効果的な短いフレーズ ---
function scoreStinger(INS, kind, t){
  if (kind==='goal'){
    INS.timp(t, nf('D2'), 0.5); INS.tick(t, 0.12, 5000, 0.6);
    ['D4','F#4','A4','D5'].forEach(n=>INS.brass(t, nf(n), 0.14, 0.07));
    ['E4','G#4','B4','E5'].forEach(n=>INS.brass(t+0.18, nf(n), 0.6, 0.07));
  } else if (kind==='snitch'){
    INS.swell(t, 1.4, 0.12);
    ['A5','C#6','E6','A6','C#7'].forEach((n,i)=>INS.celesta(t+1.2+i*0.07, nf(n), 0.08));
  } else if (kind==='catch'){
    INS.timp(t, nf('D2'), 0.5); INS.tick(t, 0.15, 4000, 1.2);
    ['D5','F#5','A5','D6','F#6','A6'].forEach((n,i)=>INS.celesta(t+i*0.06, nf(n), 0.09));
    ['D4','F#4','A4'].forEach(n=>INS.brass(t+0.1, nf(n), 1.2, 0.06));
  } else if (kind==='win'){
    const seq = [['D4',0,0.16],['F#4',0.18,0.16],['A4',0.36,0.16],['D5',0.54,1.6]];
    seq.forEach(([n,dt,d])=>{ INS.brass(t+dt, nf(n), d, 0.09); INS.brass(t+dt, nf(n)/2, d, 0.05); });
    ['D4','F#4','A4','D5'].forEach(n=>INS.strings(t+0.54, nf(n), 2.2, 0.03));
    for (let i=0;i<10;i++) INS.timp(t+0.54+i*0.07, nf('D2'), 0.08+i*0.025);
    INS.tick(t+1.25, 0.18, 3500, 2.2);
    ['D6','F#6','A6','D7'].forEach((n,i)=>INS.celesta(t+0.7+i*0.1, nf(n), 0.07));
  } else if (kind==='lose'){
    ['A5','F5','D5','A4'].forEach((n,i)=>INS.celesta(t+i*0.32, nf(n), 0.09));
    ['D4','F4','A4'].forEach(n=>INS.pad(t, nf(n), 2.4, 0.02));
    INS.bass(t, nf('D2'), 2.4, 0.1);
  } else if (kind==='draw'){
    ['D5','E5','A4','D5'].forEach((n,i)=>INS.celesta(t+i*0.28, nf(n), 0.09));
    ['D4','G4','A4'].forEach(n=>INS.pad(t, nf(n), 2.0, 0.02));
  }
}

// --- 一度だけ録音してキャッシュ。重い合成は OfflineAudioContext 内で完了させる。 ---
const MUSIC_SR = 32000, MUSIC_TAIL = 4;
const STINGER_LENGTH = {goal:3.5, snitch:5, catch:5, win:7, lose:7, draw:6};
const musicYield = () => new Promise(resolve=>setTimeout(resolve,0));
async function renderMusic(key){
  if (key==='match' || key==='tension') throw new Error('Use tools/build-match-music.py for the sampled action cues');
  seed = Array.from(key).reduce((h,c)=>(Math.imul(h,31)+c.charCodeAt(0))>>>0,20261114);
  const OC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  if (!OC) throw new Error('OfflineAudioContext is unavailable');
  const sting = key.startsWith('fx:'), name = key==='tension' ? 'match' : key;
  const S = sting ? null : SONGS[name], intense = key==='tension';
  const bars = sting ? 0 : S.chords.length*S.passes;
  const seconds = sting ? STINGER_LENGTH[key.slice(3)] : bars*S.spb*60/(S.bpm*(intense?1.09:1)*S.div);
  const frames = Math.round(seconds*MUSIC_SR), tail = sting ? 0 : MUSIC_SR*MUSIC_TAIL;
  const a = new OC(2,frames+tail,MUSIC_SR), INS = createMusicInstruments(a);
  if (sting) scoreStinger(INS,key.slice(3),0);
  else {
    const sl = frames/MUSIC_SR/(bars*S.spb);
    for (let b=0;b<bars;b++){
      for (let s=0;s<S.spb;s++) playStep(INS,name,b,s,(b*S.spb+s)*sl,sl,intense);
      // ノードを組む短い処理もまとめてメインスレッドを占有しない。
      if (b%2===1) await musicYield();
    }
  }
  const rendered = await a.startRendering(), out = a.createBuffer(2,frames,MUSIC_SR);
  // 最後の残響を先頭へ折り返し、ループの境目でも音を切らない。
  let peak = 0;
  for (let c=0;c<2;c++){
    const src = rendered.getChannelData(c), dst = out.getChannelData(c);
    dst.set(src.subarray(0,frames));
    for (let i=0;i<tail;i++) dst[i%frames] += src[frames+i]*Math.min(1,(tail-i)/(MUSIC_SR*0.05));
    if (sting){
      for (let i=0;i<MUSIC_SR*0.003;i++) dst[i] *= i/(MUSIC_SR*0.003);
      for (let i=0;i<MUSIC_SR*0.03;i++) dst[frames-1-i] *= i/(MUSIC_SR*0.03);
    }
    for (let i=0;i<frames;i++) peak = Math.max(peak,Math.abs(dst[i]));
  }
  const level = Math.min(2,0.68/Math.max(peak,0.001));
  for (let c=0;c<2;c++){
    const dst = out.getChannelData(c);
    for (let i=0;i<frames;i++) dst[i] *= level;
    await musicYield();
  }
  return out;
}

window.renderQuidditchMusic = renderMusic;
window.quidditchMusicKeys = ['menu',...Object.keys(STINGER_LENGTH).map(k=>'fx:'+k)];
})();

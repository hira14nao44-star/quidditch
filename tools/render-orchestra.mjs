// Development-only SoundFont renderer. Requires spessasynth_core 4.4.10.
// node tools/render-orchestra.mjs bank.sf2 score.mid rendered.wav [engine-module]
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const [bankPath,midiPath,outputPath,enginePath] = process.argv.slice(2);
if (!bankPath || !midiPath || !outputPath) throw new Error('Expected SoundFont, MIDI and output paths');
const {SoundBankLoader,SpessaSynthProcessor,SpessaSynthSequencer,BasicMIDI,audioToWav,SpessaLog} =
  await import(enginePath ? pathToFileURL(enginePath).href : 'spessasynth_core');
SpessaLog.setLogLevel(false,false,false);
const asArrayBuffer = b=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
const bank = SoundBankLoader.fromArrayBuffer(asArrayBuffer(await fs.readFile(bankPath)));
const midi = BasicMIDI.fromArrayBuffer(asArrayBuffer(await fs.readFile(midiPath)));
const rate = 44100, synth = new SpessaSynthProcessor(rate,{eventsEnabled:false});
synth.soundBankManager.addSoundBank(bank,'orchestra');
await synth.ready;
synth.setSystemParameter('autoAllocateVoices',true);
const seq = new SpessaSynthSequencer(synth);
seq.loadNewSongList([midi]); seq.play();
const frames = Math.ceil(rate*(midi.duration+4));
const left = new Float32Array(frames), right = new Float32Array(frames);
for (let i=0;i<frames;i+=128){
  seq.processTick(); synth.process(left,right,i,Math.min(128,frames-i));
}
await fs.writeFile(outputPath,new Uint8Array(audioToWav([left,right],rate)));
console.log('Rendered sampled orchestra:',outputPath);

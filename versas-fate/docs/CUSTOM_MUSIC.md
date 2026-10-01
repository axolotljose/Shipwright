# Custom music for Versa's Fate

The mod ships three pieces of music, in their **own optional archive**:

| Track | In `VersasFate-Music.o2r` as | What it is for |
|---|---|---|
| Versas Vine Forest | `custom/music/versasfate/Versas Vine Forest_bgm` | the forest theme |
| Versa Gohma | `custom/music/versasfate/Versa Gohma_bgm` | the boss theme |
| Versas Lullaby | `custom/music/versasfate/Versas Lullaby_fanfare` | the ocarina melody |

**`VersasFate.o2r` - the mod itself - contains no music at all.** With only that
installed, every track you hear is vanilla (the Minuet jingle on warp, Saria's
theme in the forest, the vanilla boss theme). That is the shipped default: the
mod never hands the audio engine a sequence file of its own, so it cannot be the
cause of an audio problem. `VersasFate-Music.o2r` is a separate 1 KB archive you
copy into `mods/` as well if you want the custom tracks.

SoH reads music out of an archive from the `custom/music/` folder and turns
every entry it finds into a *custom sequence* that you can then assign to any
vanilla music slot in the in-game Audio Editor. That is the whole mechanism,
and it is entirely data: nothing in this folder needs the C++ patch.

---

## 1. The honest version of "convert my mp3"

The N64 audio engine is a **note** player. A `.seq` file is a script of
note-on/note-off events plus a program (instrument) number; the sound comes
from the sound fonts that ship with the game. There is no code path in SoH
that plays a streamed OGG/MP3 as background music out of a `.o2r`, which is
why "convert my mp3 into a `.seq`" can only mean one of two things:

1. **Transcribe it** - keep the melody and the rhythm and let the game's own
   instruments play it. This is what `tools/audio_to_seq.py` does, and it is
   what the mod ships by default.
2. **Build a real custom instrument** - encode your track as an audio sample
   and write a sound font that plays it. This *is* possible with libultraship
   (the `Sample` and `SoundFont` XML resources support `CustomFormat="ogg"`),
   it is what `.ootrs` music packs with a custom bank do, and it is currently
   marked "not supported yet" by SoH's own `.ootrs` loader. See section 4.

Nothing else exists. If a guide tells you to drop an `.ogg` into `mods` and
expect a soundtrack, it is wrong.

---

## 2. Transcribe your track (the supported path)

### 2.1 Requirements

* Python 3.9+ (no third-party modules - no pip install needed).
* *Only if your source is not a `.wav`*: `ffmpeg` on your PATH.
  On Windows the easy way is `winget install Gyan.FFmpeg`, or download a
  build from <https://www.gyan.dev/ffmpeg/builds/>, unzip it and add its `bin`
  folder to PATH. Check with `ffmpeg -version` in a new terminal.

### 2.2 Convert

From the `versas-fate` folder:

```bat
python tools\audio_to_seq.py "C:\music\vine_forest.mp3" -o music\versas_vine_forest.seq --bpm 96 --voices 3
python tools\audio_to_seq.py "C:\music\gohma.mp3"      -o music\versa_gohma.seq       --bpm 140 --voices 3
python tools\audio_to_seq.py "C:\music\lullaby.wav"    -o music\versas_lullaby.seq    --bpm 72
```

Options that matter:

| Option | Meaning |
|---|---|
| `--bpm N` | the tempo of the source track. This sets the slice length (one slice = one 1/8 note) **and** the sequence tempo. If the result sounds too fast/slow, this is the knob. |
| `--voices 1..3` | split the transcription into melody / middle / bass channels. 3 sounds much fuller; 1 is the most robust. |
| `--program N` | which instrument from the game's sound font plays it. Try `1` (piano), `6`, `11`, `48`, `66`. |
| `--quiet-db -46` | slices quieter than this become rests. Raise it (e.g. `-40`) if the transcription is noisy, lower it (`-55`) if notes are missing. |

Then rebuild the archive:

```bat
python tools\build_versas_fate.py
```

`build_versas_fate.py` wraps the `.seq` in the Sequence resource header the
engine expects, so you never have to touch binary formats by hand.

It also runs `tools/validate_seq.py` over every file in `music/` before packing,
and so should you after converting:

```bat
python tools\validate_seq.py music\*.seq
```

That decodes the bytecode with the same rules as `audio_seqplayer.c` and fails
on the things that make a song silent rather than crash - an offset written in
the wrong encoding, a layer pointer one byte off, a channel script that ends
before its layer can play, a note delay of zero. Check the printed length too:
it should be roughly the length of your track.

### 2.3 What you get, and what you don't

You get the melody, the rhythm, and the game's instrument. You do not get
chords (one note per channel per slice), vocals, drums as drums (loud
percussion usually becomes wrong notes), or the original mix's timbre. A busy
track transcribes badly - a clean melodic line transcribes well. If the result
is not good enough, use section 4.

---

## 3. Assigning it in game

*(With `VersasFate-Music.o2r` installed. Without it there is nothing here to
assign, and the game plays vanilla music.)*

The mod's music is registered as *custom* sequences; the game will not use
them until you point a vanilla slot at them. That is a one-time, per-save-file
click in the **Audio Editor**:

1. Start the game and load a save.
2. **Enhancements -> Audio Editor -> Popout Audio Editor Window**
   (the padlock button at the bottom right of the window unlocks editing).
3. Assign:
   * Forest theme: **Background Music** tab -> row **"Lost Woods"** ->
     dropdown -> **"Versas Vine Forest"**.
     (The scene's `<SetSoundSettings SeqId="62">` is `NA_BGM_SARIA_THEME`,
     which is the "Lost Woods" row, so this is the slot the forest plays.)
   * Boss theme: **Battle Music** tab -> row **"Battle"** -> dropdown ->
     **"Versa Gohma"**. Field scenes switch to the "Battle" sequence
     automatically when enemies are near, which is how the hollow gets its
     own theme without any code.
     You can also assign it to the **"Boss Battle"** row if you prefer.
   * Melody: see below.
4. Close the Audio Editor. The choice is saved to your config immediately.

### The melody, exactly

Our C++ patch plays `Audio_PlayFanfare(NA_BGM_OCA_MINUET)` when you play
"Versa's Lullaby", so by default you hear the vanilla Minuet of Forest
jingle. SoH's Audio Editor only offers *fanfare* custom sequences in the
**Fanfares** tab and *ocarina* sequences in the **Ocarina** tab; a mod-shipped
sequence can only ever be the former (`AudioCollection::AddToCollection`
categorises mod music as BGM or Fanfare - there is no way to ship an
"ocarina" sequence from an archive). If you want your own melody to play:

1. Open `patch/soh/soh/VersasFateWarp.cpp` and change one line:

   ```c
   #define VF_WARP_FANFARE NA_BGM_OCA_MINUET   ->   #define VF_WARP_FANFARE NA_BGM_APPEAR
   ```

   (`NA_BGM_APPEAR` is "Enter Zelda", a fanfare that only plays during one
   cutscene, so hijacking it is harmless.)
2. Rebuild the game.
3. Audio Editor -> **Fanfares** tab -> row **"Enter Zelda"** -> dropdown ->
   **"Versas Lullaby"**.

---

## 4. The high-fidelity route (custom sound font)

If transcription is not good enough and you want your actual recording, the
port has all the pieces, but you have to build a full custom sound font:

1. Encode your track as **OGG/Opus** (mono or stereo, 32 kHz is plenty).
2. Ship it in the archive, for example at `custom/fonts/versasfate/sample`
   with a sibling `sample.meta` (or as a `<Sample ...>` XML resource).
3. Write a `<SoundFont Version="0" Num="..." Medium="..." CachePolicy="..."
   Data1="..." Data2="..." Data3="...">` XML with one `<Instruments>` entry
   whose note map points at that sample, so any note plays your recording.
4. Write a `<Sequence Version="0" Streamed="false" ...><Font FontIdx="0"/>
   </Sequence>` XML whose `Path` is the raw `.seq` that plays one very long
   note.

Field names for `Sample` and `SoundFont` are in
`soh/soh/resource/importer/AudioSampleFactory.cpp` and
`soh/soh/resource/importer/AudioSoundFontFactory.cpp` (both are readable XML
importers). This is the `.ootrs` "custom bank" path that SoH currently refuses
to load from a music pack, so it is advanced, undocumentedly-supported
territory: expect to iterate. The note-based path in section 2 is what the mod
is built and tested around.

---

## 5. Adding more tracks

Add an entry to `SEQUENCES` in `tools/build_versas_fate.py`:

```python
dict(file="my_new_track.seq", label="My Track", part="bgm", default=dict(font=0)),
```

Name it without underscores (`My Track`, not `My_Track`): SoH builds the
display label of a custom sequence from the file name up to the first
underscore, and the `_bgm` / `_fanfare` suffix at the end of the archive entry
is what marks it as music or as a jingle.

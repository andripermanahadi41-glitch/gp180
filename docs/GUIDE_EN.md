> **WIP GP-180**: format .prst, protokol USB, model dan preset masih data GP-200. Lihat GP180_PORTING_NOTES.md.

# GP-180 Studio — User Guide (V0.91)

## What is it?

GP-180 Studio generates presets (`.prst` files) for your **Valeton GP-180**
from a simple text description. You write what you want to hear, an AI creates
the preset, and all you have to do is send it directly to the GP-180 via USB.

Description examples:
- *"Crystal clean tone with chorus and spring reverb"*
- *"Warm blues crunch, Stevie Ray Vaughan style"*
- *"Modern metal, saturated gain, tight gate, slapback delay"*
- *"Pink Floyd lead tone with long delay and lush reverb"*


## Requirements

- **Python 3.10+** installed (check *"Add python.exe to PATH"* during installation)
- **Tkinter** included (this is the default on Windows if you check
  *"tcl/tk and IDLE"* during Python installation)
- **An API key** for at least one of the supported AI providers (see below)
- **For the Batch LUFS module only**: `pip install sounddevice pyloudnorm`
  (not required for preset generation)

Preset generation only uses Python's standard library.


## Installation

1. Extract the zip contents into a folder of your choice
2. Copy `config.example.json` to `config.json`
3. Open `config.json` with a text editor and paste your API key
4. Double-click `GP180_Studio.bat` (or run `python gp180_studio.py`)

On first launch, the application will ask you to choose the GP-180 injection
slot and configure your API keys through a graphical interface.


## Getting an API key

The application needs an API key to communicate with an AI service.
**This key is personal and calls are generally billed to you.**
Here are the options:

### Google Gemini — recommended for beginners
- **Cost**: free (limited quota but sufficient for normal use)
- **Credit card**: not required
- **Link**: https://aistudio.google.com/app/apikey
- **Procedure**: sign in with your Google account, click *"Create API Key"*,
  copy the generated key

### Anthropic Claude
- **Cost**: pay-per-use (~$0.003 to $0.015 per preset depending on the model)
- **Credit card**: required (prepaid credits, minimum ~$5)
- **Link**: https://console.anthropic.com/settings/keys

### OpenAI (ChatGPT)
- **Cost**: pay-per-use (~$0.002 to $0.01 per preset depending on the model)
- **Credit card**: required (prepaid credits)
- **Link**: https://platform.openai.com/api-keys

### OpenRouter
- **Cost**: pay-per-use, access to dozens of models
- **Authentication**: via OAuth (no key to enter manually —
  a *Sign in* button opens the browser and retrieves the key automatically)
- **Link**: https://openrouter.ai

### Perplexity
- **Cost**: pay-per-use (web search included in the price)
- **Credit card**: required
- **Link**: https://www.perplexity.ai/settings/api

**Security**: your API key is stored locally in your `config.json`,
encrypted on Windows via DPAPI. It is never sent anywhere other than the
AI provider you have chosen.


## The interface

```
+------------------------------------------------------------------------+
| GP-180 STUDIO   New / Refine   Language  ⚙ Config  ★ Features          |
+--------------------+---------------------------------------------------+
|  OPTIONS           |  DESCRIBE THE SOUND YOU WANT                      |
|   provider         |  [ text input area ]                              |
|   model            |  EXAMPLES                                         |
|   guitar pickup    |  SONG STRUCTURE                                   |
|   web search       |                                                   |
|                    |  SIGNAL CHAIN   <displayed preset name>           |
|  GENERATED PRESETS |  [PRE][WAH][DST][AMP][NR][CAB][EQ][MOD][DLY]...  |
|   > variant A      |  +-----------------------------------------+     |
|     variant B      |  | AMP  J-120 CL               module 4/11 |     |
|     variant C      |  | GAIN 25   BASS 40   MIDDLE 50   ...      |     |
|     ...            |  +-----------------------------------------+     |
|                    |                                                   |
|                    |  Result | Log                                     |
|                    |  [ detailed report ]                              |
+--------------------+---------------------------------------------------+
| ● status   📍 01-A   🔌 Inject          Setlist | ⚡ Generate presets   |
+------------------------------------------------------------------------+
```

The interface adapts to your screen resolution. The window opens at 90% of
the screen, centered. It has dark mode only.

### The signal chain

The 11 preset modules are displayed **on a single line**, in the real chain
order, connected by a cable like on a pedalboard. The color indicates the
module's role:

| Color | Modules | Role |
|---|---|---|
| **Blue** | `PRE`, `DST`, `AMP` | what shapes the tone |
| **Green** | `NR`, `CAB`, `EQ` | what refines it |
| **Purple** | `WAH`, `MOD`, `DLY`, `RVB`, `VOL` | what colors it |

A dotted module is **bypassed**: on the GP-180 a slot is never empty,
it is simply disabled.

During generation, **the cable lights up module by module** and a glowing dot
travels along it — that's the progress indicator.

### The module inspector

**Click on a module** in the chain: all its settings appear just below,
with a gauge for values between 0 and 100.

The chain cards only show one parameter (with a `+5` indicating how many
others are waiting). **The cards show the signal path, the inspector shows
the values.** This display is read-only.

### The live slot editor

Clicking on a module **from a loaded or generated preset** opens a
**Live Control** window if the GP-180 is connected via USB. You can change
the effect model and adjust its parameters in real time, directly on the
hardware, without re-pushing the entire preset. Changes are reflected in the
`.prst` file and visible in the inspector.

### The GP-180 LED

At the bottom left, the **● GP-180** indicator shows the USB connection status:
- **Green**: USB SysEx + Audio detected (injection + LUFS available)
- **Orange**: USB SysEx only (injection OK, no USB audio)
- **Grey**: GP-180 not detected

### Navigating generated presets

One generation writes 3 variants per section, up to 9 files at once.
The left column lists them all under **GENERATED PRESETS**.

Clicking a preset recomposes the chain and, if the GP-180 is connected,
automatically injects it into the configured slot (📍). The displayed preset
name appears next to the *Signal chain* title.


## Usage

### Generating presets ("New" mode)

1. Choose your **AI provider** and **model** from the dropdown menus
2. Select the **pickup type** (humbucker, single coil, P90, active) so the AI
   adapts gain and EQ to your guitar
3. Write your description in the text area (or choose an example)
4. Enable or disable **web search** (helps the AI identify an artist's real
   gear, but uses more tokens)
5. Choose the **structure**:
   - **Auto-detect**: the AI decides how many presets to create and how to
     organise them (3, 6 or 9 presets)
   - **Force roles**: check the roles you want
     (`clean`, `crunch`, `disto`, `lead`) — 3 presets per role
6. Click **Generate**
7. The `.prst` files are written to the output folder
   (default: `Documents\GP180_Presets`) and appear in the left list.
   If the GP-180 is connected, the first preset is automatically injected
   into the configured slot.

### Refining a preset ("Refine" mode)

1. Switch to **Refine** mode via the selector at the top
2. Load an existing `.prst` file: its chain is displayed immediately,
   before any AI call
3. Describe the desired changes in plain text
   (*"more gain"*, *"remove the delay"*, *"change the amp to a Fender"*)
4. Click **Refine**
5. The application shows the **actual changes** calculated on the file
   (not what the model claims to have done), the updated chain,
   and any warnings (e.g. amp without a Volume parameter)

The original preset is never modified: a new version is written in a
timestamped subfolder.

### Optimise for live performance

In Refine mode, the **Live Ready** button adapts a home preset for
high-volume playing: reduction of gain and reverb/delay mixes, high-cut on
the cabinet to reduce fizz, slight mid boost. The artistic intent and creative
EQ are preserved. No description needed — the prompt is pre-wired.

### Injecting a preset onto the GP-180 (USB)

The **🔌 Inject** button at the bottom right sends the selected preset
directly to the GP-180 via USB SysEx.

- The **target slot** is permanently displayed (📍 01-A by default) and
  configurable by clicking the slot button
- A **progress bar** chunk by chunk confirms the transfer (7 packets)
- Injection is also **automatic** on each selection in the list,
  if the option is enabled in the slot dialog
- The **GP-180 must be connected via USB** and recognised (green or orange LED)

### Volume harmonisation (Batch LUFS)

Accessible via the **★ Features → 🎛 Batch Vol.** menu.

The Batch LUFS module measures the actual volume of each preset (EBU R128
standard) and automatically calibrates them to a common target, without
manual intervention.

**How it works**:
1. Load the `.prst` files in the order they are imported on the GP-180
2. Configure the audio input (GP-180 USB interface) and the test slot
3. Click **Launch**
4. For each preset: play a chord in a loop — the app measures the LUFS
   and adjusts parameters via USB in real time
5. Automatic validation after 3 seconds of stability within tolerance (±0.4 dB)

**Adjustment cascade** (most transparent to least transparent):
- **Amp Volume** (if the model has one) — range 25–100
- **CAB Volume** — range 20–100
- **Global Patch Volume** — range 35–100
- **Amp Gain** as a last resort (+10 pts max above the initial value,
  only if the amp has no separate volume)

Two preset types: **NORMAL** (target -16 dB LUFS) and **LEAD** (target -11 dB
LUFS). Corrected files are saved in an `out/` subfolder.

**Requirement**: `pip install sounddevice pyloudnorm`

> ⚠️ **USB Audio driver required for Batch LUFS**: for the application to
> measure the GP-180 audio signal, the Valeton USB Audio driver must be
> installed on your PC. Without it, the *Line (Valeton GP-180)* interface does
> not appear in the audio input list and LUFS measurement is impossible.
>
> The driver tested on Windows 11 is available here:
> https://www.valeton.net/wpfd_file/valeton-usb-asio-driver-v5-57-2-setup-zip/
>
> **Note**: this link is provided for reference only. It worked on the
> development setup (Windows 11), but there is no guarantee this driver will
> work on your PC. If you have issues, check the Valeton website
> (https://www.valeton.net) or the GP-180 user forums.

### Changing language

Use the language dropdown at the top. The change is immediate and persists
between sessions. Available languages: French, English, Spanish.

### Configuring API keys and output folder

**⚙ Config** menu at the top right:
- **API Keys**: input dialog for all providers
- **Output folder**: opens the current folder in the file explorer


## Sending presets to the GP-180

Use the **🔌 Inject** button at the bottom right: the selected preset is sent
directly to the configured slot (📍) via USB SysEx. This is the only transfer
method supported by GP-180 Studio.


## Usage tracking

If you use a paid provider (Claude, OpenAI, Perplexity), the application
displays an estimated cost for each generation. This tracking is a local
estimate — verify your actual balance on the provider's website.

You can set a spending cap in `config.json` (`budget_usd`).

Gemini (Google) does not provide client-side usage data: cost tracking is not
available for this provider.


## Common issues

| Symptom | Solution |
|---------|----------|
| *"Invalid API key"* | Check the key (no leading/trailing spaces) and the selected provider |
| *"Model not recognised"* | The AI hallucinated a name — rephrase your description |
| GP-180 not detected (grey LED) | Check the USB cable and that the Valeton driver is installed |
| Injection failed | Unplug/replug the GP-180 and try again |
| Batch: no sound measured | Check that the Valeton USB Audio driver is installed and that the audio input points to *Line (Valeton GP-180)* |
| Batch: `sounddevice` not found | `pip install sounddevice pyloudnorm` |
| App won't start | Check Python in PATH (`python --version`) and Tkinter (`python -c "import tkinter"`) |
| Network error / timeout | Check your internet connection and that the AI provider is reachable |
| Chain displayed on multiple rows | The window is too narrow — widen it or go fullscreen |
| Interface looks too big or too small | It scales to your screen resolution at startup. Restart after a resolution or Windows scaling change. |

> **Note**: the interface has dark mode only. The light/dark toggle from
> previous versions has been removed.

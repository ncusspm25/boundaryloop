# Record the actual terminal demo

No GIF/video is bundled. The CLI output is real; the provider fixture is explicitly labeled mock.
Use your existing screen recorder or an already installed asciinema. Do not install recording
tools solely to make a release asset. Do not render a fake terminal animation.

Run `python scripts/record_demo.py` in a plain terminal at approximately 100 columns. It invokes
the installed production CLI, first showing bounded failure/escalation/recovery, then a separate
human-decision stop. The script writes no credentials and uses synthetic source only. Its work
directory is temporary; its initial path and random run ids need not appear in a public recording.

Target narration and timing are in [the demo script](../launch/demo-script.md). Timing depends on
your machine; there is no artificial claim of a 35-second live model task. For the human scenario,
keep the generated directory if you want to record an actual typed rejection and resume; follow
`boundaryloop demo --scenario human --directory demo-decision` instead of the cleanup script.

Inspect any recording for personal terminal titles, paths, notifications and tokens before
publishing. An optional recording must demonstrate the real CLI and remain labeled mock.

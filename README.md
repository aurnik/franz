# Franz

A synth sound-design assistant. A musician describes a change in plain language; an LLM
observes the current sound spectrally, reasons about it using a hand-authored signal-flow
document, and surgically adjusts Pigments parameters in Reaper. Under the hood it's an MCP
(Model Context Protocol) server — any MCP-capable LLM client can connect to it.

Named for Franz Xaver Süssmayr — Mozart's assistant, who completed the *Requiem* after
Mozart died with it unfinished.

![Franz in Claude Desktop — diagnosing harshness on a distorted patch by reasoning about harmonic content vs. an EQ peak](docs/example.png)

## Using it

Right now Franz only drives Arturia Pigments inside Reaper. If that's your setup, start at
[`adapters/plugins/pigments/SETUP.md`](adapters/plugins/pigments/SETUP.md) — it walks
through the patch Pigments has to be loaded with for the parameter map to line up.

## Contributing

Contributions are welcome for new adapters. Right now there is just one DAW (Reaper) and
one synth (Arturia Pigments). To add another DAW or another synth, see the READMEs inside
`/adapters/daws/` and `/adapters/plugins/` — Reaper and Pigments are the worked examples
to copy from.

## License

MIT — see [LICENSE](LICENSE).

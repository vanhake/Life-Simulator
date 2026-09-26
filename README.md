# Life-Simulator

Simulator für Leben und Evolution: Kleine Minions suchen auf einer prozedural
erzeugten Karte nach Früchten, folgen der Maslowschen Bedürfnispyramide,
bilden Gruppen und entwickeln sich über Generationen weiter.

Den vollständigen Umsetzungsplan beschreibt [PLAN.md](PLAN.md).
**Aktueller Stand: Phase 2 (Evolution) abgeschlossen.**

- Prozedurale Karte mit Wiese, Wald, Sumpf, Berg und Fels
- Bäume mit je einer Frucht, die nachwächst; Bäume altern, sterben und säen sich aus
- Tag/Nacht (nachts geringere Sicht) und Jahreszeiten (im Winter kaum Früchte)
- Minions mit 13 Genen; sie suchen Futter, altern, suchen Partner und bekommen Kinder
- Vererbung durch Crossover und Mutation; Stammbaum mit Eltern, Kindern und Nachkommen

## Installation

```bash
pip install -r requirements.txt
```

## Starten

```bash
python -m lifesim                                  # mit Grafik
python -m lifesim --seed 3 --minions 100 --width 160 --height 100
python -m lifesim --headless --ticks 100000        # ohne Grafik, gibt Kennzahlen aus
```

## Steuerung

| Taste | Funktion |
|---|---|
| Leertaste | Pause / Weiter |
| `+` / `-` | Tempo (0,25x bis 64x) |
| `N` | Einzelschritt (in der Pause) |
| WASD / Pfeile, rechte Maustaste ziehen | Karte bewegen |
| Mausrad | Zoom |
| Linksklick | Minion auswählen |
| `F` | Ausgewähltem Minion folgen |
| Pos1 | Ganze Karte zeigen |
| `R` | Neustart |

## Tests

```bash
python -m pytest
```

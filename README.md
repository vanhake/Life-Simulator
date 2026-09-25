# Life-Simulator

Simulator für Leben und Evolution: Kleine Minions suchen auf einer prozedural
erzeugten Karte nach Früchten, folgen der Maslowschen Bedürfnispyramide,
bilden Gruppen und entwickeln sich über Generationen weiter.

Den vollständigen Umsetzungsplan beschreibt [PLAN.md](PLAN.md).
**Aktueller Stand: Phase 1 (Fundament).**

## Installation

```bash
pip install -r requirements.txt
```

## Starten

```bash
python -m lifesim                                  # mit Grafik
python -m lifesim --seed 3 --minions 100 --width 160 --height 100
python -m lifesim --headless --ticks 20000         # ohne Grafik, gibt Kennzahlen aus
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

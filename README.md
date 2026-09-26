# Life-Simulator

Ein Simulator für Leben und Evolution. Kleine *Minions* leben auf einer zufällig
erzeugten Landkarte, suchen Früchte, schlafen, bilden Gruppen, kämpfen, teilen,
fliehen vor Raubtieren und bekommen Kinder. Jeder Minion hat eigene Gene; über die
Generationen setzen sich die Eigenschaften durch, die in der jeweiligen Welt am
besten funktionieren.

Den Umsetzungsplan und die Designentscheidungen beschreibt [PLAN.md](PLAN.md).

## Installation

Benötigt Python 3.11 oder neuer.

```bash
pip install -r requirements.txt
```

## Starten

```bash
python -m lifesim                          # mit Grafik
python -m lifesim --preset raubtierwelt    # mit einer Voreinstellung
python -m lifesim --load saves/schnellspeicher.lifesim
python -m lifesim --list-presets           # Voreinstellungen anzeigen
```

Weitere Optionen: `--seed`, `--minions`, `--predators`, `--width`, `--height`
(überschreiben die Voreinstellung). `python -m lifesim --help` zeigt alle.

### Ohne Grafik

Für lange Läufe und Auswertungen:

```bash
python -m lifesim --headless --days 40 --preset hungersnot --export --save ende.lifesim
```

Gibt regelmäßig Kennzahlen aus, schreibt am Ende auf Wunsch CSV-Dateien nach
`exports/` und speichert den Spielstand. `--ticks` statt `--days` ist ebenfalls möglich,
und `--load` setzt einen gespeicherten Lauf fort.

## Die Welt

- **Karte:** Wiese, Wald, Sumpf, Berg und unpassierbarer Fels. Sumpf und Berg bremsen.
- **Bäume** tragen je höchstens eine Frucht, die nachwächst. Bäume altern, sterben und
  säen sich aus; Wald ist dichter bewachsen als Wiese.
- **Tag und Nacht:** Nachts sehen Minions schlechter und schlafen meist.
- **Jahreszeiten:** Im Sommer wachsen Früchte schnell, im Winter kaum. Jeder Winter
  ist ein Engpass, den nur gut angepasste Minions überstehen.
- **Raubtiere** jagen vor allem nachts, bevorzugt einzelne und junge Minions. Sie
  vermehren sich bei guter Ernährung und verhungern, wenn die Beute knapp wird.
  Sterben alle aus, wandern im Frühling oder Sommer neue zu.

## Die Minions

**Gene** (Werte von 0 bis 1, vererbt von beiden Eltern, mit Mutation): Geschwindigkeit,
Stärke, Energiespeicher, Stoffwechsel, Sichtweite, Lebensspanne, Fruchtbarkeit,
Bewegungsbedarf sowie die Persönlichkeit aus Aggression, Geselligkeit, Altruismus,
Neugier und Ängstlichkeit. Jedes Gen hat einen Preis: Schnelle Minions verbrauchen
mehr Energie, starke haben einen höheren Grundumsatz, langlebige werden später
erwachsen.

**Bedürfnisse nach Maslow**, von unten nach oben:

1. Physiologie: Sättigung, Schlaf, Bewegung
2. Sicherheit: Abstand zu Raubtieren und bedrohlichen Fremden
3. Soziales: Zugehörigkeit und Partnerschaft
4. Anerkennung: steigt durch Kinder, gewonnene Kämpfe, Teilen und gemeinsame Abwehr
5. Selbstverwirklichung: neue Gegenden erkunden

Höhere Stufen motivieren erst, wenn die unteren ausreichend gedeckt sind. Aus
Bedürfnissen und Persönlichkeit wählt jeder Minion seine nächste Aktion: Futter
suchen, schlafen, ausruhen, umherstreifen, fliehen, Gesellschaft suchen, Partner
suchen, erkunden, kämpfen oder teilen.

**Soziales:** Gemeinsam verbrachte Zeit, Verwandtschaft und geteiltes Futter schaffen
Freundschaft, Kämpfe schaffen Feindschaft. Aus engen Freundschaften entstehen von
selbst **Gruppen** mit einem Anführer. Verbündete helfen einander im Kampf, und eine
Gruppe, die zusammensteht, kann ein Raubtier vertreiben.

## Oberfläche

Links die Karte, rechts die Seitenleiste mit Werkzeugleiste (Pause, Einzelschritt,
Tempo, Turbo) und vier Reitern:

- **Übersicht:** Kennzahlen, Verlauf von Minions, Raubtieren und Gruppen und die
  Entwicklung aller Gene. Mit der Maus über einem Diagramm erscheinen die Werte.
- **Minion:** alles über den ausgewählten Minion oder das Raubtier: Bedürfnispyramide,
  Bedürfnisse, Gene, Familie, Beziehungen, Erfahrung. Lebende Verwandte und Bekannte
  lassen sich anklicken.
- **Einstellungen:**
  - *Spielstand:* speichern, laden, CSV exportieren.
  - *Voreinstellungen:* eine auswählen und starten, oder die aktuellen Werte unter
    eigenem Namen sichern.
  - *Welt, Minions, Raubtiere:* Schieberegler, die sofort wirken.
  - *Neue Welt:* Seed, Anzahl, Kartengröße, Baumdichte, Tages- und
    Jahreszeitenlänge; wirken beim Neustart.
- **Hilfe:** Tastenkürzel und Legende der Symbole.

### Tastenkürzel

| Taste | Funktion |
|---|---|
| Leertaste | Pause / Weiter |
| `+` / `-` | Tempo (0,25x bis 64x) |
| `T` | Turbo: so schnell wie möglich |
| `N` | Einzelschritt (in der Pause) |
| WASD / Pfeile, rechte Maustaste ziehen | Karte bewegen |
| Mausrad | Zoom über der Karte, Scrollen in der Seitenleiste |
| Linksklick | Minion oder Raubtier auswählen |
| `F` | Ausgewähltem folgen |
| Pos1 | Ganze Karte zeigen |
| `G` | Minions nach Genen oder nach Gruppe einfärben |
| `R` | Neustart |
| `F5` / `F9` | Schnell speichern / laden |
| `E` | Statistik als CSV exportieren |
| `1` – `4` | Reiter wechseln |

## Voreinstellungen

| Name | Worum es geht |
|---|---|
| `standard` | Ausgewogene Welt mit Jahreszeiten, Gruppen und einigen Raubtieren |
| `paradies` | Viel Futter, keine Raubtiere: große Population, soziale Effekte im Vordergrund |
| `hungersnot` | Wenige Bäume, magere Früchte: harte Winter, Druck auf sparsame Minions |
| `raubtierwelt` | Viele Raubtiere, die sich schnell vermehren: Wettrüsten um Tempo und Wachsamkeit |
| `schnelle_evolution` | Starke Mutationen, kurze Jahreszeiten: Gene ändern sich schnell sichtbar |
| `grosse_welt` | Weite Karte mit vielen Minions und Raubtieren (braucht einen schnellen Rechner) |

Eigene Voreinstellungen landen als JSON in `presets/` und enthalten nur die Werte,
die vom Standard abweichen. Sie lassen sich auch von Hand schreiben:

```json
{
  "titel": "Wüste",
  "beschreibung": "Kaum Bäume",
  "werte": {"tree_density": 0.015, "fruit_energy": 35.0}
}
```

## Dateien

- **Spielstände** (`saves/*.lifesim`) enthalten den kompletten Zustand inklusive
  Zufallsgenerator: Ein geladener Lauf geht genau so weiter wie der ursprüngliche.
  Sie sind komprimierte Python-Pickles, lade daher nur Spielstände, die du selbst
  erstellt hast.
- **CSV-Exporte** (`exports/`): `verlauf_*.csv` enthält eine Zeile je Messpunkt
  (alle 30 Ticks) mit Population, Todesursachen, Gruppen, Raubtieren und den
  Mittelwerten aller Gene. `minions_*.csv` enthält eine Zeile je lebendem Minion.
  Die Dateien nutzen Semikolon und Dezimalkomma, damit ein deutsches Excel sie direkt
  öffnet. In Python: `pandas.read_csv(pfad, sep=";", decimal=",")`.

## Entwicklung

```bash
python -m pytest
```

Der Simulationskern (`lifesim/core`, `world`, `agents`, `social`) kommt ohne pygame
aus und ist deterministisch: Gleicher Seed ergibt denselben Verlauf. Die Oberfläche
(`lifesim/ui`) liest nur den Zustand. Die UI-Tests laufen ohne Bildschirm.

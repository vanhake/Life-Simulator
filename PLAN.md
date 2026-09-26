# Life-Simulator – Umsetzungsplan

Ein 2D-Simulator für Leben und Evolution: Kleine *Minions* leben auf einer
prozedural erzeugten Kachelkarte, folgen der Maslowschen Bedürfnispyramide,
bilden soziale Gruppen, pflanzen sich fort und entwickeln sich über
Generationen weiter.

## 1. Getroffene Entscheidungen

| Thema | Entscheidung |
|---|---|
| Plattform | Python 3.11+, Desktop, **pygame-ce** + **pygame_gui**, numpy |
| Sprache | UI deutsch, Code/Kommentare englisch |
| Karte | 2D von oben, Kachelgitter, prozedural per Noise (Wiese, Wald, Sumpf, Berg, Fels) |
| Terrain | Bewegungskosten je Terrain, Fels unpassierbar |
| Bäume | max. 1 Frucht pro Baum, wächst nach; Bäume vermehren sich und sterben |
| Zeit | Tag/Nacht (Sichtweite) und Jahreszeiten (Fruchtwachstum) |
| KI | Hybrid: Utility-KI über Maslow-Bedürfnisse, Gene steuern Persönlichkeit |
| Maslow | Alle 5 Stufen, vereinfacht (siehe Abschnitt 4) |
| Fortpflanzung | Sexuell, zwei Eltern, Crossover + Gauß-Mutation |
| Konflikte | Kampf um Früchte und Teilen von Futter |
| Gruppen | Emergent über Beziehungswerte, Anführer nach Status |
| Raubtiere | Einstellbare Startanzahl, eigene Population (Hunger, Fortpflanzung, Tod), **keine** Evolution; Gruppen können sie gemeinsam vertreiben |
| Skalierung | flüssig bis ca. 300 Minions; Turbo-Modus ohne Rendering |
| Grafik | Einfache Formen: Farbe/Größe aus Genen, Gruppenring, Aktions-Icon |
| UI | Einstellungs-Panel, Live-Graphen, Minion-Inspektor, Zoom & Scrollen |
| Extras | Seed, Speichern/Laden, CSV-Export, Presets |

## 2. Architektur

Strikte Trennung von **Simulationskern** (reines Python/numpy, ohne pygame,
deterministisch, testbar) und **Darstellung** (pygame, liest nur den Zustand).

```
lifesim/
  __main__.py            Einstieg: python -m lifesim
  config.py              SimConfig (dataclass) + Laden/Speichern von Presets
  presets/               *.json: paradies, hungersnot, raubtierwelt, ...
  core/
    simulation.py        Simulation: fester Tick, Reihenfolge der Systeme
    rng.py               zentraler, geseedeter Zufall
    clock.py             Tageszeit, Jahreszeit
    spatial.py           Spatial Hash für Nachbarsuche
  world/
    noise.py             Perlin-/Value-Noise (numpy, keine Zusatz-Dependency)
    terrain.py           Terrain-Typen, Kosten, Generierung
    trees.py             Bäume, Fruchtwachstum, Vermehrung, Absterben
    pathfinding.py       A* auf dem Grid mit Terrainkosten (begrenzte Reichweite)
  agents/
    genome.py            Gene (0..1), Mapping auf reale Werte, Crossover, Mutation
    minion.py            Zustand eines Minions (Energie, Alter, Bedürfnisse, ...)
    needs.py             Maslow-Bedürfnisse, Sättigung, Gating
    brain.py             Utility-KI: Aktionen bewerten, Aktion wählen
    actions.py           Aktionen: essen, suchen, schlafen, fliehen, kämpfen, ...
    predator.py          Raubtiere
  social/
    relations.py         Beziehungswerte zwischen Minions
    groups.py            Gruppenbildung (Clustering), Anführer, Status
  stats/
    recorder.py          Zeitreihen (Population, Gen-Mittelwerte, Gruppen)
    export.py            CSV-Export
  persistence/
    save.py              Speichern/Laden des kompletten Zustands (inkl. RNG)
  ui/
    app.py               Hauptschleife, Tempo, Pause, Turbo
    camera.py            Zoom & Pan
    renderer.py          Karte, Bäume, Minions, Raubtiere, Tag/Nacht-Overlay
    panels/settings.py   Start- und Live-Einstellungen
    panels/stats.py      Graphen (selbst gezeichnet)
    panels/inspector.py  Gene, Bedürfnis-Pyramide, Aktion, Beziehungen, Stammbaum
tests/                   pytest für den Kern
```

**Simulationsschleife:** fester Zeitschritt (Tick). Das Tempo steuert, wie
viele Ticks pro Frame laufen. Im Turbo-Modus wird nur selten gerendert.
Reihenfolge pro Tick: Uhr → Bäume → Wahrnehmung → Entscheidung →
Bewegung/Aktionen → Interaktionen (Kampf, Teilen, Paarung) → Raubtiere →
Stoffwechsel/Tod → Soziales (alle N Ticks) → Statistik (alle N Ticks).

## 3. Gene

Jedes Gen ist ein Wert von 0 bis 1 und wird auf reale Werte abgebildet. Die
Gene haben bewusst Zielkonflikte (Trade-offs):

| Gen | Wirkung | Kosten |
|---|---|---|
| speed | Bewegungstempo | Energieverbrauch ∝ speed² |
| strength | Kampfkraft, Körpergröße | höherer Grundverbrauch |
| max_energy | größerer Energiespeicher | langsamer (Gewicht) |
| metabolism | schnellere Verwertung von Nahrung | höherer Grundverbrauch |
| vision | Sichtweite (nachts reduziert) | kleiner Energieaufwand |
| lifespan | maximales Alter | später geschlechtsreif |
| fertility | kürzerer Paarungs-Cooldown | höhere Energiekosten je Kind |
| activity_need | Bewegungsbedarf: Unruhe bei Stillstand | – |
| aggression | Neigung zu Kampf/Stehlen | Verletzungsrisiko, Beziehungen leiden |
| sociability | Gewicht sozialer Bedürfnisse | – |
| altruism | Neigung, Futter zu teilen | eigene Energie |
| curiosity | Erkundungsdrang | Energie, Risiko |
| fearfulness | Fluchtdistanz | verpasst Nahrung |

Vererbung: Uniform-Crossover beider Eltern, danach Gauß-Mutation (Rate und
Stärke einstellbar), Werte werden auf 0 bis 1 begrenzt.
Aussehen: Farbton aus Persönlichkeitsgenen, Größe aus strength, Helligkeit
aus speed. So ist Evolution direkt sichtbar.

## 4. Maslow-Bedürfnisse

Jedes Bedürfnis hat eine Sättigung von 0 bis 1. Die Dringlichkeit ergibt sich
aus `(1 − Sättigung) × Gen-Gewicht × Gate`. Das Gate ist weich: Höhere Stufen
werden gedämpft, solange niedrigere Stufen schlecht gedeckt sind. Akute
Gefahr (Raubtier in Fluchtdistanz) übersteuert alles.

| Stufe | Bedürfnis | Mechanik |
|---|---|---|
| 1 Physiologisch | Hunger, Schlaf, Bewegung | Früchte essen; nachts oder bei Erschöpfung schlafen; activity_need erzeugt Unruhe bei Stillstand |
| 2 Sicherheit | Schutz | Abstand zu Raubtieren und aggressiven Minions; Heimatgebiet; Schutz in der Gruppe |
| 3 Soziales | Zugehörigkeit, Partnerschaft | Nähe zu Freunden/Gruppe; Partnerwahl und Paarung |
| 4 Anerkennung | Status | Status steigt durch gewonnene Kämpfe, Teilen, Nachwuchs und Vertreiben von Raubtieren |
| 5 Selbstverwirklichung | Erkunden, Können | Unbekannte Gebiete erkunden (Gedächtnis-Heatmap); „Fertigkeit“ im Futterfinden wächst mit Erfahrung |

**Utility-KI:** Jede Aktion (essen gehen, schlafen, fliehen, Gruppe suchen,
Partner suchen, teilen, kämpfen, erkunden, umherstreifen) erhält einen Score
aus den Dringlichkeiten und den Persönlichkeitsgenen, ergänzt um etwas
Rauschen. Hysterese verhindert ständiges Umentscheiden.

## 5. Soziales und Konflikte

- **Beziehungen:** Sparse-Map (Minion-Paar → Wert −1 bis 1). Positiv durch
  Nähe, Teilen, Verwandtschaft und gemeinsame Abwehr; negativ durch Kämpfe
  und Diebstahl. Beziehungen verblassen langsam.
- **Gruppen:** Alle N Ticks werden Verbindungskomponenten über Beziehungen
  oberhalb einer Schwelle berechnet. Gruppen-IDs werden stabil weitergeführt
  (größte Überlappung mit der alten Gruppe). Der Anführer ist das Mitglied
  mit dem höchsten Status.
- **Kampf:** um eine Frucht oder aus Aggression. Gewinnwahrscheinlichkeit
  richtet sich nach strength und Energie. Verlierer verlieren Energie und
  fliehen; der Gewinner erhält Status und die Frucht.
- **Teilen:** Satte, altruistische Minions geben Energie an hungrige
  Freunde oder Verwandte ab.
- **Raubtier-Abwehr:** Übersteigt die Summe der strength naher
  Gruppenmitglieder einen Schwellwert, wird das Raubtier vertrieben.

## 6. Welt

- **Terrain per Noise:** Höhe und Feuchte ergeben Wiese, Wald, Sumpf, Berg
  und Fels. Die Kosten sind z. B. Wiese 1, Wald 1,5, Sumpf 2,5, Berg 3,
  Fels unpassierbar.
- **Bäume:** Dichte je Terrain (Wald hoch, Berg niedrig). Jeder Baum trägt
  höchstens eine Frucht; die Nachwachszeit hängt von der Jahreszeit ab.
  Bäume streuen gelegentlich Samen in die Nähe, haben ein Höchstalter und
  sterben dann ab. Eine maximale Baumdichte verhindert Überwucherung.
- **Tag/Nacht:** reduziert Sichtweite und erhöht den Schlafdruck; die Karte
  wird abgedunkelt.
- **Jahreszeiten:** Im Winter wachsen kaum Früchte, im Sommer viele. Das
  erzeugt Selektionsdruck.
- **Raubtiere:** Sie haben Hunger, jagen Minions in Sichtweite, ruhen,
  vermehren sich bei guter Ernährung und verhungern sonst. So entstehen
  Räuber-Beute-Zyklen.

## 7. Oberfläche

- **Karte:** Zoom per Mausrad, Verschieben mit Rechtsklick-Ziehen oder WASD.
  Ein Minion ist ein Kreis in Genfarbe mit farbigem Gruppenring und einem
  Aktionssymbol. Raubtiere sind rote Dreiecke, Bäume grüne Kreise mit
  Fruchtpunkt.
- **Einstellungs-Panel:** Startwerte (Anzahl Minions und Raubtiere,
  Kartengröße, Seed, Baumdichte, …) und Live-Werte (Tempo, Mutationsrate,
  Fruchtwachstum, Tageslänge, …). Dazu Start, Pause, Schritt, Neustart und
  Turbo.
- **Statistik:** Zeitreihen für Population, Raubtiere, Früchte, Gruppen und
  Gen-Mittelwerte (auswählbar).
- **Inspektor:** Klick auf einen Minion zeigt Gene als Balken, die
  Bedürfnis-Pyramide eingefärbt nach Sättigung, die aktuelle Aktion, Alter,
  Generation, Eltern und Kinder sowie die stärksten Beziehungen. Die Kamera
  kann dem Minion folgen.
- **Tastatur:** Leertaste für Pause, `+`/`-` für das Tempo, `F5`/`F9` für
  Speichern/Laden, `E` für den CSV-Export.

## 8. Phasen

Nach jeder Phase ist das Programm lauffähig, getestet und committet.

1. ✅ **Fundament:** Projektstruktur, Config, RNG/Seed, Noise-Terrain, Bäume mit
   nachwachsender Frucht, Minions mit Körpergenen, Hunger/Energie, Suchen und
   Essen von Früchten, Bewegung mit Terrainkosten, Tod durch Hunger. Rendering
   mit Kamera, Pause und Tempo. Tests für den Kern.
2. ✅ **Evolution:** Alter und Lebensspanne, sexuelle Fortpflanzung,
   Crossover/Mutation, Generationen, Stammbaum-Daten. Baumvermehrung,
   Tag/Nacht und Jahreszeiten.
3. ✅ **Maslow-KI:** alle Bedürfnisse, Persönlichkeitsgene, Utility-Brain,
   Schlaf, Bewegungsbedarf, Erkunden, A*-Pfadfindung.
4. **Soziales:** Beziehungen, Gruppen, Status/Anführer, Kampf und Teilen.
5. **Raubtiere:** Population, Jagd, Fortpflanzung, Gruppenabwehr.
6. **UI komplett:** pygame_gui-Einstellungspanel, Graphen, Inspektor.
7. **Extras:** Speichern/Laden, CSV-Export, Presets, Turbo-Modus,
   README/Bedienungsanleitung.

## 9. Qualität

- pytest für den Kern: Determinismus (gleicher Seed ergibt gleichen Verlauf),
  Genetik, Bedürfnis-Gating, Pfadfindung und Gruppenbildung.
- Balancing über Presets und einen Headless-Lauf
  (`python -m lifesim --headless --ticks 50000`), der Kennzahlen ausgibt.

# TTC Interactive Website

This repo contains a small static website for exploring TTC stops and historical network metrics. The site is made from one HTML file and one generated JavaScript data file.

## Files

- `ttc_interactive.html` - the interactive Leaflet map, controls, popups, legends, and layer switching.
- `ttc_metric_layers.js` - generated metric data used by the map, including service intensity, transit hub scores, route productivity, delay totals, and interrupted-route counts.


## Map Layers

- **Mode**: shows TTC stops by mode: bus, streetcar, subway, and other.
- **Service Intensity**: shows scheduled stop visits from the bundled GTFS `stop_times` data.
- **Transit Hubs**: highlights stops or station groups with more connected routes and modes.
- **Productivity**: shows 2024 passengers per vehicle hour by route.
- **Network Disruptions**: shows historical delay minutes by bus/streetcar route or subway station.
- **Interrupted Routes**: shows historical bus and streetcar records classified as diversions or off-route service.

## Data Coverage

The disruption data is historical, not live/current TTC service status:

- Bus disruptions: 2014-01-01 to 2019-11-30
- Streetcar disruptions: 2014-01-02 to 2019-12-31
- Subway disruptions: 2014-01-01 to 2019-12-31
- Productivity data: 2019-2024 annual surface statistics, with the map using 2024 values

Station closures were not kept as a website layer because the local subway disruption file only contained one explicit station-closure record.

## Notes

The website is meant as a lightweight visualization companion to the TTC network-analysis project. It does not run routing algorithms directly in the browser; it displays prepared stop, route, and disruption metrics for accessible map exploration.

/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class StationMapComponent extends Component {
    static template = "infrastructure_management.StationMapTemplate";

    setup() {
        this.mapContainer = useRef("map");
        this.map = null;
        this.lines = [];
        this.stations = [];
        this.lineStations = [];

        onWillStart(async () => {
            await Promise.all([
                loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
                loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
            ]);
            await this.loadLineData();
            await this.loadStationData();
            await this.loadLineStationData();
        });

        onMounted(() => {
            this.renderMap();
        });
    }

    async loadLineData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.line/search_read", {
            model: "infrastructure.line",
            method: "search_read",
            args: [],
            kwargs: {
                fields: ["code", "color", "departure_station_id", "terminus_station_id"],
            },
        });
        this.lines = response;
        console.log("Loaded lines:", this.lines);
    }

    async loadStationData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.station/search_read", {
            model: "infrastructure.station",
            method: "search_read",
            args: [],
            kwargs: {
                fields: ["name_en", "name_ar", "name_fr", "latitude", "longitude"],
            },
        });
        this.stations = response;
        console.log("Loaded stations:", this.stations);
    }

    async loadLineStationData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.line.station/search_read", {
            model: "infrastructure.line.station",
            method: "search_read",
            args: [],
            kwargs: {
                fields: ["line_id", "station_id", "order", "direction", "lat", "lng"],
                order: "order ASC",
            },
        });
        this.lineStations = response;
        console.log("Loaded line stations:", this.lineStations);
    }

    renderMap() {
        if (!this.mapContainer.el || !window.L) {
            console.error("Map container not found or Leaflet not loaded!");
            return;
        }

        const defaultCoords = [36.365, 6.6147];
        this.map = L.map(this.mapContainer.el).setView(defaultCoords, 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);

        this.drawLines();
        this.drawStations();

        // Fit map to all markers
        const bounds = [];
        this.stations.forEach(station => {
            if (station.latitude && station.longitude) {
                bounds.push([station.latitude, station.longitude]);
            }
        });
        this.lineStations.forEach(ls => {
            if (ls.lat && ls.lng) {
                bounds.push([ls.lat, ls.lng]);
            }
        });
        if (bounds.length > 0) {
            this.map.fitBounds(bounds);
        }
    }

    drawLines() {
        this.lines.forEach(line => {
            // Find departure and terminus stations
            const departureStation = this.stations.find(s => s.id === line.departure_station_id[0]);
            const terminusStation = this.stations.find(s => s.id === line.terminus_station_id[0]);

            // Filter line stations for this line
            const lineStations = this.lineStations
                .filter(ls => ls.line_id && ls.line_id[0] === line.id)
                .filter(ls => ls.lat && ls.lng);

            // Split stations into GOING and RETURNING
            const goingStations = lineStations
                .filter(ls => ls.direction === 'GOING')
                .sort((a, b) => a.order - b.order); // Ascending order

            const returningStations = lineStations
                .filter(ls => ls.direction === 'RETURNING')
                .sort((a, b) => b.order - a.order); // Descending order

            console.log(`GOING stations for line ${line.code}:`, goingStations);
            console.log(`RETURNING stations for line ${line.code}:`, returningStations);

            // Draw departure marker
            if (departureStation && departureStation.latitude && departureStation.longitude) {
                L.circleMarker([departureStation.latitude, departureStation.longitude], {
                    radius: 8,
                    fillColor: '#007bff',
                    color: '#fff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }).bindPopup(`<b>Departure:</b> ${line.code}<br><b>Name:</b> ${departureStation.name_en}`).addTo(this.map);
            }

            // Draw terminus marker
            if (terminusStation && terminusStation.latitude && terminusStation.longitude) {
                L.circleMarker([terminusStation.latitude, terminusStation.longitude], {
                    radius: 8,
                    fillColor: '#ff7800',
                    color: '#fff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }).bindPopup(`<b>Terminus:</b> ${line.code}<br><b>Name:</b> ${terminusStation.name_en}`).addTo(this.map);
            }

            // Draw GOING polyline (departure → stations → terminus) in green
            const goingCoordinates = [];
            if (departureStation && departureStation.latitude && departureStation.longitude) {
                goingCoordinates.push([departureStation.latitude, departureStation.longitude]);
            }
            goingStations.forEach(ls => {
                goingCoordinates.push([ls.lat, ls.lng]);
            });
            if (terminusStation && terminusStation.latitude && terminusStation.longitude) {
                goingCoordinates.push([terminusStation.latitude, terminusStation.longitude]);
            }

            console.log(`GOING polyline coordinates for line ${line.code}:`, goingCoordinates);
            if (goingCoordinates.length >= 2) {
                L.polyline(goingCoordinates, {
                    color: '#00ff00', // Green for GOING
                    weight: 4,
                    opacity: 0.7,
                    dashArray: '5, 5'
                }).addTo(this.map).bindPopup(`<b>Line:</b> ${line.code} (Going)`);
            } else {
                console.warn(`Not enough points to draw GOING polyline for line ${line.code}`);
            }

            // Draw RETURNING polyline (terminus → stations → departure) in red
            const returningCoordinates = [];
            if (terminusStation && terminusStation.latitude && terminusStation.longitude) {
                returningCoordinates.push([terminusStation.latitude, terminusStation.longitude]);
            }
            returningStations.forEach(ls => {
                returningCoordinates.push([ls.lat, ls.lng]);
            });
            if (departureStation && departureStation.latitude && departureStation.longitude) {
                returningCoordinates.push([departureStation.latitude, departureStation.longitude]);
            }

            console.log(`RETURNING polyline coordinates for line ${line.code}:`, returningCoordinates);
            if (returningCoordinates.length >= 2) {
                L.polyline(returningCoordinates, {
                    color: '#ff0000', // Red for RETURNING
                    weight: 4,
                    opacity: 0.7,
                    dashArray: '5, 5'
                }).addTo(this.map).bindPopup(`<b>Line:</b> ${line.code} (Returning)`);
            } else {
                console.warn(`Not enough points to draw RETURNING polyline for line ${line.code}`);
            }
        });
    }

    drawStations() {
        console.log("Drawing line stations:", this.lineStations);
        this.lineStations.forEach(ls => {
            if (!ls.lat || !ls.lng) {
                console.warn("Skipping line station with missing lat/lng:", ls);
                return;
            }

            // Find the line and station
            const line = this.lines.find(l => l.id === ls.line_id[0]);
            const station = this.stations.find(s => s.id === ls.station_id[0]);
            const lineCode = line ? line.code : 'Unknown';
            const stationName = station ? station.name_en : 'Unknown';

            // Use different colors for GOING and RETURNING stations
            const fillColor = ls.direction === 'GOING' ? '#00ff00' : ls.direction === 'RETURNING' ? '#ff0000' : '#666666';

            // Add station marker
            L.circleMarker([ls.lat, ls.lng], {
                radius: 5,
                fillColor: fillColor,
                color: '#fff',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.6
            }).bindPopup(
                `<b>Station:</b> ${stationName}<br>` +
                `<b>Line:</b> ${lineCode}<br>` +
                `<b>Direction:</b> ${ls.direction}<br>` +
                `<b>Names:</b><br>` +
                `  - Arabic: ${station ? station.name_ar : 'Unknown'}<br>` +
                `  - French: ${station ? station.name_fr : 'Unknown'}`
            ).addTo(this.map);
        });
    }
}

registry.category("actions").add("station_map_tag", StationMapComponent);
/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class LineMapComponent extends Component {
    static template = "line_test.LineMapTemplate";

    setup() {
        this.mapContainer = useRef("map");
        this.map = null;
        this.lines = [];
        this.stations = [];

        onWillStart(async () => {
            await Promise.all([
                loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
                loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
            ]);
            await this.loadLineData();
            await this.loadStationData();
        });

        onMounted(() => {
            this.renderMap();
        });
    }

    async loadLineData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/line.management/search_read", {
            model: "line.management",
            method: "search_read",
            args: [],
            kwargs: {
                fields: ["code", "color", "departure_lat", "departure_lng", "terminus_lat", "terminus_lng"],
            },
        });
        this.lines = response;
        console.log("Loaded lines:", this.lines);
    }

    async loadStationData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/line.station/search_read", {
            model: "line.station",
            method: "search_read",
            args: [],
            kwargs: {
                fields: ["station_name_en", "line_id", "lat", "lng", "order", "direction"],
            },
        });
        this.stations = response;
        console.log("Loaded stations:", this.stations);
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
        this.lines.forEach(line => {
            if (line.departure_lat && line.departure_lng) {
                bounds.push([line.departure_lat, line.departure_lng]);
            }
            if (line.terminus_lat && line.terminus_lng) {
                bounds.push([line.terminus_lat, line.terminus_lng]);
            }
        });
        this.stations.forEach(station => {
            if (station.lat && station.lng) {
                bounds.push([station.lat, station.lng]);
            }
        });
        if (bounds.length > 0) {
            this.map.fitBounds(bounds);
        }
    }

    drawLines() {
        this.lines.forEach(line => {
            // Filter stations for this line
            const lineStations = this.stations
                .filter(station => station.line_id && station.line_id[0] === line.id)
                .filter(station => station.lat && station.lng);

            // Split stations into GOING and RETURNING
            const goingStations = lineStations
                .filter(station => station.direction === 'GOING')
                .sort((a, b) => a.order - b.order); // Ascending order

            const returningStations = lineStations
                .filter(station => station.direction === 'RETURNING' || station.direction === 'RETURN')
                .sort((a, b) => b.order - a.order); // Descending order

            console.log(`GOING stations for line ${line.code}:`, goingStations);
            console.log(`RETURNING stations for line ${line.code} (before sorting):`, returningStations.map(s => ({ id: s.id, order: s.order })));
            console.log(`RETURNING stations for line ${line.code} (after sorting):`, returningStations.map(s => ({ id: s.id, order: s.order })));

            // Draw departure marker
            if (line.departure_lat && line.departure_lng) {
                L.circleMarker([line.departure_lat, line.departure_lng], {
                    radius: 8,
                    fillColor: '#007bff',
                    color: '#fff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }).bindPopup(`<b>Departure:</b> ${line.code}`).addTo(this.map);
            }

            // Draw terminus marker
            if (line.terminus_lat && line.terminus_lng) {
                L.circleMarker([line.terminus_lat, line.terminus_lng], {
                    radius: 8,
                    fillColor: '#ff7800',
                    color: '#fff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }).bindPopup(`<b>Terminus:</b> ${line.code}`).addTo(this.map);
            }

            // Draw GOING polyline (departure → stations → terminus) in green
            const goingCoordinates = [];
            if (line.departure_lat && line.departure_lng) {
                goingCoordinates.push([line.departure_lat, line.departure_lng]);
            }
            goingStations.forEach(station => {
                goingCoordinates.push([station.lat, station.lng]);
            });
            if (line.terminus_lat && line.terminus_lng) {
                goingCoordinates.push([line.terminus_lat, line.terminus_lng]);
            }

            console.log(`GOING polyline coordinates for line ${line.code}:`, goingCoordinates);
            if (goingCoordinates.length >= 2) {
                L.polyline(goingCoordinates, {
                    color: '#00ff00', // Green for GOING
                    weight: 4,
                    opacity: 0.7,
                    dashArray: '5, 5'
                }).addTo(this.map);
            } else {
                console.warn(`Not enough points to draw GOING polyline for line ${line.code}`);
            }

            // Draw RETURNING polyline (terminus → stations (highest to lowest order) → departure) in red
            const returningCoordinates = [];
            const returningOrderSequence = []; // To log the order sequence
            if (line.terminus_lat && line.terminus_lng) {
                returningCoordinates.push([line.terminus_lat, line.terminus_lng]);
                returningOrderSequence.push("Terminus");
            }
            returningStations.forEach(station => {
                returningCoordinates.push([station.lat, station.lng]);
                returningOrderSequence.push(`Station (order: ${station.order})`);
            });
            if (line.departure_lat && line.departure_lng) {
                returningCoordinates.push([line.departure_lat, line.departure_lng]);
                returningOrderSequence.push("Departure");
            }

            console.log(`RETURNING polyline coordinates for line ${line.code}:`, returningCoordinates);
            console.log(`RETURNING path sequence for line ${line.code}:`, returningOrderSequence);
            if (returningCoordinates.length >= 2) {
                L.polyline(returningCoordinates, {
                    color: '#ff0000', // Red for RETURNING
                    weight: 4,
                    opacity: 0.7,
                    dashArray: '5, 5'
                }).addTo(this.map);
            } else {
                console.warn(`Not enough points to draw RETURNING polyline for line ${line.code}`);
            }
        });
    }

    drawStations() {
        console.log("Drawing stations:", this.stations);
        this.stations.forEach(station => {
            if (!station.lat || !station.lng) {
                console.warn("Skipping station with missing lat/lng:", station);
                return;
            }

            // Find the line to get its code
            const line = this.lines.find(l => l.id === station.line_id[0]); // line_id is [id, name]
            const lineCode = line ? line.code : 'Unknown';

            // Use different colors for GOING and RETURNING stations
            const fillColor = (station.direction === 'GOING') ? '#00ff00' : (station.direction === 'RETURNING' || station.direction === 'RETURN') ? '#ff0000' : '#666666';

            // Add station marker
            L.circleMarker([station.lat, station.lng], {
                radius: 5, // Smaller than departure/terminus markers
                fillColor: fillColor,
                color: '#fff',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.6
            }).bindPopup(`<b>Station:</b> ${station.station_name_en || 'Unknown'}<br><b>Line:</b> ${lineCode}<br><b>Direction:</b> ${station.direction}`).addTo(this.map);
        });
    }
}

registry.category("actions").add("line_map_tag", LineMapComponent);
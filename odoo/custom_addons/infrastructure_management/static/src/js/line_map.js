/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class LineMapComponent extends Component {
    static template = "infrastructure_management.line_map";

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
        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.line/search_read", {
            model: "infrastructure.line",
            method: "search_read",
            args: [this.props.action.domain || []],
            kwargs: {
                fields: ["enterprise_code", "color", "departure_station_id", "terminus_station_id"],
                context: this.props.action.context || {},
            },
        });
        this.lines = response;
        console.log("Loaded lines:", this.lines);
    }

    async loadStationData() {
        const stationIds = [];
        this.lines.forEach(line => {
            if (line.departure_station_id) stationIds.push(line.departure_station_id[0]);
            if (line.terminus_station_id) stationIds.push(line.terminus_station_id[0]);
        });
        if (stationIds.length === 0) return;

        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.station/search_read", {
            model: "infrastructure.station",
            method: "search_read",
            args: [[["id", "in", [...new Set(stationIds)]]]],
            kwargs: {
                fields: ["name_en", "latitude", "longitude"],
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

        const bounds = [];
        this.lines.forEach(line => {
            const departureStation = this.stations.find(s => s.id === line.departure_station_id[0]);
            const terminusStation = this.stations.find(s => s.id === line.terminus_station_id[0]);
            if (departureStation && departureStation.latitude && departureStation.longitude) {
                bounds.push([departureStation.latitude, departureStation.longitude]);
            }
            if (terminusStation && terminusStation.latitude && terminusStation.longitude) {
                bounds.push([terminusStation.latitude, terminusStation.longitude]);
            }
        });
        if (bounds.length > 0) {
            this.map.fitBounds(bounds);
        } else {
            this.env.services.notification.add("No valid line coordinates found.", {
                type: "warning",
                title: "Map Warning",
            });
        }
    }

    drawLines() {
        this.lines.forEach(line => {
            const departureStation = this.stations.find(s => s.id === line.departure_station_id[0]);
            const terminusStation = this.stations.find(s => s.id === line.terminus_station_id[0]);

            if (departureStation && terminusStation && 
                departureStation.latitude && departureStation.longitude && 
                terminusStation.latitude && terminusStation.longitude) {
                const coordinates = [
                    [departureStation.latitude, departureStation.longitude],
                    [terminusStation.latitude, terminusStation.longitude],
                ];

                L.polyline(coordinates, {
                    color: line.color || '#000000',
                    weight: 5,
                    opacity: 0.7,
                }).addTo(this.map).bindPopup(`<b>Line:</b> ${line.enterprise_code}`);

                L.circleMarker([departureStation.latitude, departureStation.longitude], {
                    radius: 8,
                    fillColor: '#007bff',
                    color: '#fff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8,
                }).bindPopup(`<b>Departure:</b> ${line.enterprise_code}<br><b>Name:</b> ${departureStation.name_en}`).addTo(this.map);

                L.circleMarker([terminusStation.latitude, terminusStation.longitude], {
                    radius: 8,
                    fillColor: '#ff7800',
                    color: '#fff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8,
                }).bindPopup(`<b>Terminus:</b> ${line.enterprise_code}<br><b>Name:</b> ${terminusStation.name_en}`).addTo(this.map);
            } else {
                console.warn(`Skipping line ${line.enterprise_code} due to missing station coordinates`);
            }
        });
    }
}

registry.category("actions").add("line_map_tag", LineMapComponent);
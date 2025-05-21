/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class LineStationMapComponent extends Component {
    static template = "infrastructure_management.LineStationMapTemplate";

    setup() {
        this.mapContainer = useRef("map");
        this.map = null;
        this.lineStations = [];
        this.lines = [];
        this.stations = [];

        onWillStart(async () => {
            await Promise.all([
                loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
                loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
            ]);
            await this.loadLineStationData();
            await this.loadLineData();
            await this.loadStationData();
        });

        onMounted(() => {
            this.renderMap();
        });
    }

    async loadLineStationData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.line.station/search_read", {
            model: "infrastructure.line.station",
            method: "search_read",
            args: [this.props.action.domain || []],
            kwargs: {
                fields: ["order", "direction", "lat", "lng", "line_id", "station_id", "external_id"],
                context: this.props.action.context || {},
            },
        });
        this.lineStations = response;
        console.log("Loaded line stations:", this.lineStations);
    }

    async loadLineData() {
        const lineIds = [...new Set(this.lineStations.map(ls => ls.line_id[0]))];
        if (lineIds.length === 0) return;

        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.line/search_read", {
            model: "infrastructure.line",
            method: "search_read",
            args: [[["id", "in", lineIds]]],
            kwargs: {
                fields: ["enterprise_code", "color"],
            },
        });
        this.lines = response;
        console.log("Loaded lines:", this.lines);
    }

    async loadStationData() {
        const stationIds = [...new Set(this.lineStations.map(ls => ls.station_id[0]))];
        if (stationIds.length === 0) return;

        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.station/search_read", {
            model: "infrastructure.station",
            method: "search_read",
            args: [[["id", "in", stationIds]]],
            kwargs: {
                fields: ["name_en", "name_ar", "name_fr", "latitude", "longitude"],
            },
        });
        this.stations = response;
        console.log("Loaded stations:", this.stations);
    }

    openLineStationForm(lineStationId) {
        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'infrastructure.line.station',
            res_id: lineStationId,
            views: [[false, 'form']],
            view_mode: 'form',
            target: 'current',
        });
    }

    renderMap() {
        if (!this.mapContainer.el || !window.L) {
            console.error("Map container not found or Leaflet not loaded!");
            return;
        }

        const defaultCoords = [36.365, 6.6147];
        this.map = L.map(this.mapContainer.el).setView(defaultCoords, 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19,
        }).addTo(this.map);

        // Add legend control
        const legend = L.control({ position: 'topright' });
        legend.onAdd = () => {
            const div = L.DomUtil.create('div', 'info legend');
            div.style.backgroundColor = 'white';
            div.style.padding = '10px';
            div.style.border = '1px solid #ccc';
            div.style.borderRadius = '5px';
            div.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
            div.style.fontFamily = 'Arial, sans-serif';
            div.style.fontSize = '12px';
            div.innerHTML = `
                <div style="margin-bottom: 6px;">
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background-color: #00FF00; margin-right: 6px;"></span>GOING
                </div>
                <div>
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background-color: #FF0000; margin-right: 6px;"></span>RETURNING
                </div>
            `;
            return div;
        };
        legend.addTo(this.map);

        const bounds = [];
        // Add markers for line stations without polylines
        this.lineStations.forEach(ls => {
            const station = this.stations.find(s => s.id === ls.station_id[0]);
            const line = this.lines.find(l => l.id === ls.line_id[0]);
            if (station && station.latitude && station.longitude) {
                const latLng = [station.latitude, station.longitude];
                bounds.push(latLng);

                // Debug log to verify direction value
                console.log(`Line Station ID: ${ls.id}, Direction: ${ls.direction}, Marker Color: ${ls.direction === 'GOING' ? '#00FF00' : '#FF0000'}`);

                const markerColor = ls.direction === 'GOING' ? '#00FF00' : '#FF0000'; // Green for Going, Red for Returning
                const marker = L.marker(latLng, {
                    icon: L.divIcon({
                        className: 'custom-marker',
                        html: `<div style="background-color: ${markerColor}; width: 16px; height: 16px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>`,
                        iconSize: [16, 16],
                        iconAnchor: [8, 8],
                        popupAnchor: [0, -8],
                    }),
                    title: station.name_en || 'Station',
                });

                let popupContent = `
                    <div style="min-width: 200px; font-family: Arial, sans-serif; font-size: 14px;">
                        <h3 style="margin: 0 0 10px; font-size: 16px; color: ${markerColor};">${station.name_en || 'Unknown'}</h3>
                        <p style="margin: 5px 0;"><b>Line:</b> ${line ? line.enterprise_code : 'Unknown'}</p>
                        <p style="margin: 5px 0;"><b>Direction:</b> ${ls.direction}</p>
                        <p style="margin: 5px 0;"><b>Order:</b> ${ls.order}</p>
                        <p style="margin: 5px 0;"><b>Coordinates:</b> (${station.latitude.toFixed(4)}, ${station.longitude.toFixed(4)})</p>
                        <p style="margin: 5px 0;"><b>External ID:</b> ${ls.external_id || 'N/A'}</p>
                        <div style="margin-top: 10px;">
                            <button class="btn btn-primary btn-sm line-station-edit-btn" 
                                    data-line-station-id="${ls.id}">Edit</button>
                        </div>
                    </div>
                `;

                marker.bindPopup(popupContent, {
                    maxWidth: 300,
                    minWidth: 200,
                });

                marker.on('popupopen', () => {
                    const editButton = document.querySelector(`.line-station-edit-btn[data-line-station-id="${ls.id}"]`);
                    if (editButton) {
                        editButton.addEventListener('click', () => {
                            this.openLineStationForm(ls.id);
                        });
                    }
                });

                // Add marker directly to the map (no clustering)
                marker.addTo(this.map);
            } else {
                console.warn(`Skipping line station ${ls.id} due to missing station coordinates`);
            }
        });

        if (bounds.length > 0) {
            this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
        } else {
            this.env.services.notification.add("No valid line station coordinates found.", {
                type: "warning",
                title: "Map Warning",
            });
        }
    }
}

registry.category("actions").add("line_station_map_tag", LineStationMapComponent);
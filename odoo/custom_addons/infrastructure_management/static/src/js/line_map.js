/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class LineMapComponent extends Component {
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
        // Collect station IDs from lineStations
        const stationIdsFromLineStations = [...new Set(this.lineStations.map(ls => ls.station_id[0]))];
        // Collect station IDs from lines (departure and terminus)
        const stationIdsFromLines = [
            ...new Set(this.lines.flatMap(line => [
                line.departure_station_id ? line.departure_station_id[0] : null,
                line.terminus_station_id ? line.terminus_station_id[0] : null,
            ]).filter(id => id))
        ];
        // Combine all station IDs
        const allStationIds = [...new Set([...stationIdsFromLineStations, ...stationIdsFromLines])];
        if (allStationIds.length === 0) return;

        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.station/search_read", {
            model: "infrastructure.station",
            method: "search_read",
            args: [[["id", "in", allStationIds]]],
            kwargs: {
                fields: ["name_en", "name_ar", "name_fr", "latitude", "longitude"],
            },
        });
        this.stations = response;
        console.log("Loaded stations:", this.stations);
    }

    openLineForm(lineId) {
        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'infrastructure.line',
            res_id: lineId,
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
                    <span style="display: inline-block; width: 20px; height: 4px; background-color: #00FF00; margin-right: 6px;"></span>GOING
                </div>
                <div style="margin-bottom: 6px;">
                    <span style="display: inline-block; width: 20px; height: 4px; background-color: #FF0000; margin-right: 6px;"></span>RETURNING
                </div>
                <div style="margin-bottom: 6px;">
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background-color: #007bff; margin-right: 6px;"></span>Departure
                </div>
                <div>
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background-color: #ff7800; margin-right: 6px;"></span>Terminus
                </div>
            `;
            return div;
        };
        legend.addTo(this.map);

        const bounds = [];
        // Group line stations by line_id and direction for polylines
        const lineGroups = {};
        this.lineStations.forEach(ls => {
            const key = `${ls.line_id[0]}_${ls.direction}`;
            if (!lineGroups[key]) {
                lineGroups[key] = [];
            }
            lineGroups[key].push(ls);
        });

        // Sort each group by order and draw polylines for lines with lineStations
        Object.keys(lineGroups).forEach(key => {
            const group = lineGroups[key].sort((a, b) => a.order - b.order);
            const coordinates = [];
            group.forEach(ls => {
                const station = this.stations.find(s => s.id === ls.station_id[0]);
                if (station && station.latitude && station.longitude) {
                    coordinates.push([station.latitude, station.longitude]);
                }
            });

            if (coordinates.length > 1) {
                const line = this.lines.find(l => l.id === group[0].line_id[0]);
                const polylineColor = group[0].direction === 'GOING' ? '#00FF00' : '#FF0000'; // Green for Going, Red for Returning
                const polyline = L.polyline(coordinates, {
                    color: polylineColor,
                    weight: 5,
                    opacity: 0.7,
                }).addTo(this.map);

                // Enhanced popup with line details and edit button
                let popupContent = `
                    <div style="min-width: 200px; font-family: Arial, sans-serif; font-size: 14px;">
                        <h3 style="margin: 0 0 10px; font-size: 16px; color: ${polylineColor};">${line ? line.enterprise_code : 'Unknown'}</h3>
                        <p style="margin: 5px 0;"><b>Color:</b> ${line ? line.color || 'N/A' : 'N/A'}</p>
                        <p style="margin: 5px 0;"><b>Direction:</b> ${group[0].direction}</p>
                        <div style="margin-top: 10px;">
                            <button class="btn btn-primary btn-sm line-edit-btn" 
                                    data-line-id="${line ? line.id : ''}">Edit</button>
                        </div>
                    </div>
                `;
                polyline.bindPopup(popupContent, { maxWidth: 300, minWidth: 200 });

                polyline.on('popupopen', () => {
                    const editButton = document.querySelector(`.line-edit-btn[data-line-id="${line ? line.id : ''}"]`);
                    if (editButton) {
                        editButton.addEventListener('click', () => {
                            this.openLineForm(line ? line.id : null);
                        });
                    }
                });
            }
        });

        // Handle lines without lineStations (only departure and terminus)
        this.lines.forEach(line => {
            const hasLineStations = this.lineStations.some(ls => ls.line_id[0] === line.id);
            if (!hasLineStations && line.departure_station_id && line.terminus_station_id) {
                const departureStation = this.stations.find(s => s.id === line.departure_station_id[0]);
                const terminusStation = this.stations.find(s => s.id === line.terminus_station_id[0]);
                if (departureStation && departureStation.latitude && departureStation.longitude &&
                    terminusStation && terminusStation.latitude && terminusStation.longitude) {
                    const coordinates = [
                        [departureStation.latitude, departureStation.longitude],
                        [terminusStation.latitude, terminusStation.longitude]
                    ];
                    const polyline = L.polyline(coordinates, {
                        color: line.color || '#000000',
                        weight: 5,
                        opacity: 0.7,
                    }).addTo(this.map);

                    let popupContent = `
                        <div style="min-width: 200px; font-family: Arial, sans-serif; font-size: 14px;">
                            <h3 style="margin: 0 0 10px; font-size: 16px; color: ${line.color || '#000000'};">${line.enterprise_code || 'Unknown'}</h3>
                            <p style="margin: 5px 0;"><b>Color:</b> ${line.color || 'N/A'}</p>
                            <div style="margin-top: 10px;">
                                <button class="btn btn-primary btn-sm line-edit-btn" 
                                        data-line-id="${line.id}">Edit</button>
                            </div>
                        </div>
                    `;
                    polyline.bindPopup(popupContent, { maxWidth: 300, minWidth: 200 });

                    polyline.on('popupopen', () => {
                        const editButton = document.querySelector(`.line-edit-btn[data-line-id="${line.id}"]`);
                        if (editButton) {
                            editButton.addEventListener('click', () => {
                                this.openLineForm(line.id);
                            });
                        }
                    });

                    // Add markers for departure and terminus
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

                    coordinates.forEach(coord => bounds.push(coord));
                } else {
                    console.warn(`Skipping line ${line.enterprise_code} due to missing coordinates for departure or terminus station`);
                }
            }
        });

        // Add markers for line stations
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
                    </div>
                `;

                marker.bindPopup(popupContent, {
                    maxWidth: 300,
                    minWidth: 200,
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

registry.category("actions").add("line_map_tag", LineMapComponent);
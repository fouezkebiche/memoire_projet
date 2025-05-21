/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class StationMapComponent extends Component {
    static template = "infrastructure_management.StationMapTemplate";

    setup() {
        this.mapContainer = useRef("map");
        this.map = null;
        this.stations = [];

        onWillStart(async () => {
            await Promise.all([
                loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
                loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
                loadJS("https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"),
                loadCSS("https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"),
                loadCSS("https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"),
            ]);
            await this.loadStationData();
        });

        onMounted(() => {
            this.renderMap();
        });
    }

    async loadStationData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/infrastructure.station/search_read", {
            model: "infrastructure.station",
            method: "search_read",
            args: [this.props.action.domain || []],
            kwargs: {
                fields: ["name_en", "name_ar", "name_fr", "latitude", "longitude", "line_ids", "external_id"],
                context: this.props.action.context || {},
            },
        });
        this.stations = response;
        console.log("Loaded stations:", this.stations);
    }

    openStationForm(stationId) {
        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'infrastructure.station',
            res_id: stationId,
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

        const markerClusterGroup = L.markerClusterGroup({
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: true,
            zoomToBoundsOnClick: true,
        });

        const bounds = [];
        this.stations.forEach(station => {
            if (station.latitude && station.longitude) {
                const latLng = [station.latitude, station.longitude];
                bounds.push(latLng);

                // Use L.marker with a custom icon for better visibility
                const marker = L.marker(latLng, {
                    icon: L.divIcon({
                        className: 'custom-marker',
                        html: `<div style="background-color: #007bff; width: 24px; height: 24px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 4px rgba(0,0,0,0.5);"></div>`,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12],
                        popupAnchor: [0, -12],
                    }),
                    title: station.name_en || 'Station',
                });

                // Enhanced popup content with better styling
                let popupContent = `
                    <div style="min-width: 200px; font-family: Arial, sans-serif; font-size: 14px;">
                        <h3 style="margin: 0 0 10px; font-size: 16px; color: #007bff;">${station.name_en || 'Unknown'}</h3>
                        <p style="margin: 5px 0;"><b>Name (AR):</b> ${station.name_ar || 'N/A'}</p>
                        <p style="margin: 5px 0;"><b>Name (FR):</b> ${station.name_fr || 'N/A'}</p>
                        <p style="margin: 5px 0;"><b>Coordinates:</b> (${station.latitude.toFixed(4)}, ${station.longitude.toFixed(4)})</p>
                        <p style="margin: 5px 0;"><b>External ID:</b> ${station.external_id || 'N/A'}</p>
                `;

                if (station.line_ids && station.line_ids.length > 0) {
                    popupContent += `<p style="margin: 5px 0;"><b>Lines:</b></p><ul style="margin: 0; padding-left: 20px;">`;
                    station.line_ids.forEach(lineId => {
                        popupContent += `<li>Line ID: ${lineId}</li>`;
                    });
                    popupContent += `</ul>`;
                } else {
                    popupContent += `<p style="margin: 5px 0;"><b>Lines:</b> None</p>`;
                }

                popupContent += `
                        <div style="margin-top: 10px;">
                            <button class="btn btn-primary btn-sm station-edit-btn" 
                                    data-station-id="${station.id}">Edit</button>
                        </div>
                    </div>
                `;

                marker.bindPopup(popupContent, {
                    maxWidth: 300,
                    minWidth: 200,
                });

                // Bind click event to the marker's popup content after it's opened
                marker.on('popupopen', () => {
                    const editButton = document.querySelector(`.station-edit-btn[data-station-id="${station.id}"]`);
                    if (editButton) {
                        editButton.addEventListener('click', () => {
                            this.openStationForm(station.id);
                        });
                    }
                });

                markerClusterGroup.addLayer(marker);
            } else {
                console.warn(`Skipping station ${station.name_en || station.id} due to missing coordinates`);
            }
        });

        this.map.addLayer(markerClusterGroup);

        if (bounds.length > 0) {
            this.map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
        } else {
            this.env.services.notification.add("No valid station coordinates found.", {
                type: "warning",
                title: "Map Warning",
            });
        }
    }
}

registry.category("actions").add("station_map_tag", StationMapComponent);
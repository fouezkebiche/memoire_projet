/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class BusMapComponent extends Component {
    static template = "bus_tracking.MapClientActionTemplate";

    setup() {
        this.mapContainer = useRef("map");
        this.busData = [];
        this.map = null;
        this.busIcon = null;
        this.markers = {}; // 🆕 Store markers by bus ID

        onWillStart(async () => {
            await Promise.all([
                loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
                loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
            ]);
            await this.loadBusData();
        });

        onMounted(async () => {
            await this.renderMap();
            this.startPolling(); // 🆕 Start polling updates
        });
    }

    async loadBusData() {
        const response = await this.env.services.rpc("/web/dataset/call_kw/bus_tracking.bus/search_read", {
            model: "bus_tracking.bus",
            method: "search_read",
            args: [],
            kwargs: {
                fields: ["name", "driver", "latitude", "longitude"],
            },
        });
        this.busData = response;
        console.log("Loaded buses:", this.busData);
    }

    async renderMap() {
        if (!this.mapContainer.el || !window.L) {
            console.error("Map container not found or Leaflet not loaded!");
            return;
        }

        const defaultCoords = [36.365, 6.6147];
        this.map = L.map(this.mapContainer.el).setView(defaultCoords, 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);

        this.busIcon = L.icon({
            iconUrl: 'https://img.icons8.com/emoji/48/bus-emoji.png',
            iconSize: [35, 35],
            iconAnchor: [17, 34],
            popupAnchor: [0, -30],
        });

        this.updateMapMarkers(); // Initial markers
    }

    async startPolling() {
        setInterval(async () => {
            await this.loadBusData();
            this.updateMapMarkers(); // Update every 5 seconds
        }, 5000);
    }

    updateMapMarkers() {
        this.busData.forEach((bus) => {
            if (!bus.latitude || !bus.longitude) return;

            const newLatLng = L.latLng(bus.latitude, bus.longitude);
            const popup = `<b>🚌 ${bus.name}</b><br>👨‍✈️ ${bus.driver || "Unknown"}`;

            const existingMarker = this.markers[bus.id];

            if (existingMarker) {
                const oldLatLng = existingMarker.getLatLng();

                // 🧠 Only animate if location changed
                if (!oldLatLng.equals(newLatLng)) {
                    this.animateMarker(existingMarker, oldLatLng, newLatLng, 500);
                }

                existingMarker.setPopupContent(popup);
            } else {
                // 🆕 Add new marker
                const marker = L.marker(newLatLng, { icon: this.busIcon })
                    .addTo(this.map)
                    .bindPopup(popup);

                this.markers[bus.id] = marker;
            }
        });
    }

    // 🧙‍♂️ Magic: Smoothly move marker between points
    animateMarker(marker, from, to, duration = 500) {
        const start = performance.now();

        const animate = (time) => {
            const elapsed = time - start;
            const t = Math.min(elapsed / duration, 1);

            const lat = from.lat + (to.lat - from.lat) * t;
            const lng = from.lng + (to.lng - from.lng) * t;

            marker.setLatLng([lat, lng]);

            if (t < 1) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    }
}

registry.category("actions").add("bus_map_tag", BusMapComponent);

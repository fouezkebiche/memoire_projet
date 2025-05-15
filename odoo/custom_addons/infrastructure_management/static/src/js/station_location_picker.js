/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, useRef, onWillRender } from "@odoo/owl";

class StationLocationPicker extends Component {
    static template = "infrastructure_management.StationLocationPickerTemplate";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
        id: { type: String, optional: true },
        name: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.mapRef = useRef("map");
        this.defaultLat = 36.7538; // Algiers coordinates
        this.defaultLng = 3.0588;
        this.map = null;
        this.marker = null;

        onWillStart(() => {
            console.log("StationLocationPicker: onWillStart");
            console.log("Leaflet available:", !!window.L, "Version:", window.L?.version);
        });

        onWillRender(() => {
            console.log("StationLocationPicker: onWillRender");
            console.log("Map ref before render:", this.mapRef.el);
        });

        onMounted(() => {
            console.log("StationLocationPicker: mounted");
            console.log("Map ref after mount:", this.mapRef.el);
            if (!this.mapRef.el) {
                console.error("Map container not found in DOM");
                return;
            }

            // Log container styles and dimensions
            const styles = window.getComputedStyle(this.mapRef.el);
            const rect = this.mapRef.el.getBoundingClientRect();
            console.log("Map container styles:", {
                display: styles.display,
                width: styles.width,
                height: styles.height,
                visibility: styles.visibility,
            });
            console.log("Map container dimensions:", rect);

            if (!window.L) {
                console.error("Cannot initialize map: Leaflet is not available.");
                return;
            }

            try {
                // Initialize map
                console.log("Initializing Leaflet map...");
                this.map = window.L.map(this.mapRef.el, {
                    center: [this.defaultLat, this.defaultLng],
                    zoom: 10,
                });
                console.log("Map initialized:", this.map);

                // Add OpenStreetMap tile layer
                window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
                    maxZoom: 19,
                }).addTo(this.map);
                console.log("Tile layer added");

                // Get coordinates from record
                const lat = parseFloat(this.props.record.data.latitude || this.defaultLat);
                const lng = parseFloat(this.props.record.data.longitude || this.defaultLng);
                console.log("Record coordinates:", { lat, lng });

                if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
                    this.marker = window.L.marker([lat, lng]).addTo(this.map);
                    this.map.setView([lat, lng], 10);
                    console.log("Marker added at:", { lat, lng });
                } else {
                    console.warn("Using default coordinates:", { lat: this.defaultLat, lng: this.defaultLng });
                }

                // Add click event for non-readonly mode
                if (!this.props.readonly) {
                    this.map.on("click", (e) => {
                        const { lat, lng } = e.latlng;
                        console.log("Map clicked, new coordinates:", { lat, lng });
                        if (this.marker) {
                            this.marker.setLatLng([lat, lng]);
                        } else {
                            this.marker = window.L.marker([lat, lng]).addTo(this.map);
                        }
                        this.props.record.update({
                            latitude: lat,
                            longitude: lng,
                        });
                    });
                }
            } catch (error) {
                console.error("Error initializing map:", error);
            }
        });
    }

    willUnmount() {
        console.log("StationLocationPicker: willUnmount");
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
    }
}

registry.category("fields").add("station_location_picker", {
    component: StationLocationPicker,
    supportedTypes: ["boolean"], // Match the field type in station.py
});
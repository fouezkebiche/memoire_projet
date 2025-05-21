/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillStart, useRef, onWillUnmount } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

class RideMapComponent extends Component {
    static template = "dynamics_management.RideMapTemplate";
    static props = {
        '*': true, // Allow any props to avoid Owl validation error
    };

    setup() {
        this.mapContainer = useRef("map");
        this.map = null;
        this.rides = [];

        onWillStart(async () => {
            console.log("Loading Leaflet resources...");
            await Promise.all([
                loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
                loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
            ]);
            await this.loadRideData();
        });

        onMounted(() => {
            console.log("Rendering map...");
            this.renderMap();
        });

        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
                this.map = null;
                console.log("Map removed on unmount.");
            }
        });
    }

    async loadRideData() {
        try {
            console.log("Attempting RPC call to /web/dataset/call_kw/dynamics.ride/get_ride_map_data");
            const response = await this.env.services.rpc(
                "/web/dataset/call_kw/dynamics.ride/get_ride_map_data",
                {
                    model: "dynamics.ride",
                    method: "get_ride_map_data",
                    args: [],
                    kwargs: {},
                }
            );
            this.rides = response || [];
            console.log("Loaded rides:", JSON.stringify(this.rides, null, 2));
        } catch (error) {
            console.error("Error loading rides:", JSON.stringify(error, null, 2));
            this.env.services.notification.add("Failed to fetch ride data: " + (error.message || "Unknown error"), {
                type: "danger",
                title: "Error",
            });
        }
    }

    renderMap() {
        if (!this.mapContainer.el || !window.L) {
            console.error("Map container not found or Leaflet not loaded!");
            this.env.services.notification.add("Map container not found or Leaflet not loaded.", {
                type: "danger",
                title: "Error",
            });
            return;
        }

        const defaultCoords = [36.452488, 6.258685]; // Center on API ride coordinates
        this.map = L.map(this.mapContainer.el).setView(defaultCoords, 10);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
        }).addTo(this.map);

        this.drawRides();

        const bounds = this.rides
            .filter(ride => ride.lat && ride.lng)
            .map(ride => [ride.lat, ride.lng]);
        if (bounds.length > 0) {
            this.map.fitBounds(bounds, { padding: [50, 50] });
        } else {
            console.warn("No valid ride coordinates found.");
            this.env.services.notification.add("No rides with valid coordinates found.", {
                type: "warning",
                title: "No Rides",
            });
        }
    }

    drawRides() {
        this.rides.forEach(ride => {
            if (!ride.lat || !ride.lng) {
                console.warn("Skipping ride with missing lat/lng:", ride);
                return;
            }

            const popupContent = document.createElement('div');
            popupContent.innerHTML = `
                <b>Ride ID:</b> ${ride.external_id || "Unknown"}<br>
                <b>Direction:</b> ${ride.direction || "Unknown"}<br>
                <b>Line:</b> ${ride.line_name || "Unknown"}<br>
                <b>Vehicle:</b> ${ride.vehicle_plate || "Unknown"}<br>
                <b>Coordinates:</b> (${ride.lat}, ${ride.lng})<br>
                <div style="margin-top: 10px;">
                    <button class="btn btn-primary btn-sm o_edit_ride_button">Edit</button>
                </div>
            `;

            // Add click event listener for the Edit button
            popupContent.querySelector('.o_edit_ride_button').addEventListener('click', () => {
                this.env.services.action.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'dynamics.ride',
                    res_id: ride.id,
                    views: [[false, 'form']],
                    target: 'current',
                    context: this.env.context || {},
                });
            });

            L.marker([ride.lat, ride.lng])
                .addTo(this.map)
                .bindPopup(popupContent);
        });
    }
}

registry.category("actions").add("ride_map_tag", RideMapComponent);
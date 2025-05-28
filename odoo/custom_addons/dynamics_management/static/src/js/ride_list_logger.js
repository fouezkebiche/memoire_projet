/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

// Track whether the rides list is active and manage intervals
let isRidesListActive = false;
let urlCheckInterval = null;
let syncInterval = null;

patch(ListController.prototype, {
    setup() {
        super.setup();
        // Use a per-instance flag to prevent multiple setup calls
        if (this.props.resModel === "dynamics.ride" && !this._isRideListInitialized) {
            this._isRideListInitialized = true;
            console.log("✅ Entered Rides List view");
            isRidesListActive = true;

            // Initialize lastUrl to the current URL
            let lastUrl = window.location.href;

            // Delay sync start to ensure URL stabilization
            setTimeout(() => {
                // Extract model and view_type from URL hash
                const hash = window.location.hash;
                const hashParams = new URLSearchParams(hash.replace("#", ""));
                const initialModel = hashParams.get("model") || "";
                const initialViewType = hashParams.get("view_type") || "";
                console.log("Initial URL:", window.location.href);
                console.log("Initial model from hash:", initialModel);
                console.log("Initial view_type from hash:", initialViewType);

                // Only proceed if model is dynamics.ride and view_type is list
                if (initialModel !== "dynamics.ride" || initialViewType !== "list") {
                    console.warn("Not in Rides List view (model or view_type mismatch), skipping sync");
                    isRidesListActive = false;
                    this._isRideListInitialized = false;
                    return;
                }

                // Start automatic sync only if not already running
                if (!syncInterval) {
                    console.log("Starting automatic sync every 10 seconds");
                    syncInterval = setInterval(async () => {
                        if (isRidesListActive) {
                            try {
                                console.log("Calling sync_rides_from_api via RPC");
                                await this.env.services.rpc(
                                    "/web/dataset/call_kw/dynamics.ride/sync_rides_from_api",
                                    {
                                        model: "dynamics.ride",
                                        method: "sync_rides_from_api",
                                        args: [],
                                        kwargs: { context: { reload_view: true } },
                                    }
                                );
                                console.log("Sync completed successfully");
                                // Refresh the list view without full reload
                                this.model.load({ keepSelection: true });
                            } catch (error) {
                                console.error("Sync failed:", JSON.stringify(error, null, 2));
                                this.env.services.notification.add(
                                    "Failed to sync rides: " + (error.message || "Unknown error"),
                                    { type: "danger", title: "Sync Error" }
                                );
                            }
                        }
                    }, 10000); // 10 seconds
                }

                // Start URL monitoring for view exit
                if (!urlCheckInterval) {
                    urlCheckInterval = setInterval(() => {
                        const currentUrl = window.location.href;
                        if (currentUrl !== lastUrl && isRidesListActive) {
                            // Extract current model and view_type from hash
                            const currentHash = window.location.hash;
                            const currentHashParams = new URLSearchParams(currentHash.replace("#", ""));
                            const currentModel = currentHashParams.get("model") || "";
                            const currentViewType = currentHashParams.get("view_type") || "";
                            console.log("Current URL:", currentUrl);
                            console.log("Current model from hash:", currentModel);
                            console.log("Current view_type from hash:", currentViewType);

                            // Check if the view has changed
                            if (currentModel !== "dynamics.ride" || currentViewType !== "list") {
                                console.log("❌ Left Rides List view");
                                isRidesListActive = false;
                                this._isRideListInitialized = false;
                                // Stop both intervals
                                clearInterval(urlCheckInterval);
                                urlCheckInterval = null;
                                clearInterval(syncInterval);
                                syncInterval = null;
                                console.log("Stopped automatic sync");
                            }
                        }
                        lastUrl = currentUrl;
                    }, 500);
                }
            }, 1000); // 1 second for URL stabilization
        }
    },

    // Reset initialization and clean up intervals on destroy
    willUnmount() {
        super.willUnmount();
        this._isRideListInitialized = false;
        // Only clear intervals if this instance is the active one
        if (isRidesListActive) {
            if (syncInterval) {
                clearInterval(syncInterval);
                syncInterval = null;
                console.log("Stopped automatic sync on unmount");
            }
            if (urlCheckInterval) {
                clearInterval(urlCheckInterval);
                urlCheckInterval = null;
                console.log("Stopped URL monitoring on unmount");
            }
            isRidesListActive = false;
        }
    }
});
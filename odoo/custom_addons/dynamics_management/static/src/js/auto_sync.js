/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class AutoSyncComponent extends Component {
    static template = "dynamics_management.AutoSyncTemplate";

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.syncInterval = null;

        onMounted(() => {
            console.log("AutoSyncComponent mounted, starting sync timer");
            this.startSyncTimer();
        });

        onWillUnmount(() => {
            console.log("AutoSyncComponent unmounted, stopping sync timer");
            if (this.syncInterval) {
                clearInterval(this.syncInterval);
                this.syncInterval = null;
            }
        });
    }

    startSyncTimer() {
        this.syncInterval = setInterval(async () => {
            try {
                console.log("Calling sync_rides_from_api");
                await this.rpc("/web/dataset/call_kw/dynamics.ride/sync_rides_from_api", {
                    model: "dynamics.ride",
                    method: "sync_rides_from_api",
                    args: [],
                    kwargs: {},
                });
                console.log("Sync completed, reloading view");
                this.action.doAction({
                    type: 'ir.actions.client',
                    tag: 'reload',
                });
            } catch (error) {
                console.error("Sync error:", error);
            }
        }, 10000);
    }
}

registry.category("actions").add("dynamics_auto_sync", AutoSyncComponent);
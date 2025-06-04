/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

class DriverSearchController extends ListController {
    setup() {
        super.setup();
        this.modelName = this.props.resModel;
    }

    async _onSearch(searchQuery) {
        if (this.modelName !== "profile.driver") {
            return super._onSearch(searchQuery);
        }

        const searchValue = searchQuery.terms.join(" ").trim();
        const field = searchQuery.filters.length ? searchQuery.filters[0].fieldName : "first_name";

        if (!searchValue) {
            return super._onSearch(searchQuery);
        }

        try {
            const result = await this.env.services.rpc({
                route: "/profiles/drivers/search",
                params: {
                    search_term: searchValue,
                    field: field,
                },
            });
            this.model.load({
                resIds: result.records.map(record => record.id),
                limit: result.length,
                offset: 0,
            });
            this.render();
        } catch (error) {
            console.error("Search error:", error);
            return super._onSearch(searchQuery);
        }
    }
}

registry.category("view_controllers").add("driver_search_controller", DriverSearchController);
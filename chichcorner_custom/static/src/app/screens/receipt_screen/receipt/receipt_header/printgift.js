/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    /**
     * Override the export_for_printing method to include loyalty card details.
     */
    export_for_printing() {
        // Call the original method using `super`
        const receipt = super.export_for_printing(...arguments);
        // Add loyalty card details to the receipt
        if (this.loyalty_card_ids) {
            receipt.loyalty_card_ids = this.loyalty_card_ids;
        }
        console.log("Receipt card ",receipt)
        return receipt;
    },
});
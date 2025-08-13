/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {

    async _processData(loadedData) {
        await super._processData(loadedData);
        // Process partner categories 07/08/2025
        if (loadedData['res.partner.category']) {
            this.partner_categories = loadedData['res.partner.category'];
            console.log("[DEBUG] Loaded partner categories:", this.partner_categories);
        }
    },
    getReceiptHeaderData() {
       const order = this.get_order();
       const product = order.get_orderlines()?.[0]?.get_product();
       const now = new Date();
       const orderDate = now.toISOString().split('T')[0]; // YYYY-MM-DD
       const orderTime = now.toTimeString().split(' ')[0]; // HH:MM:SS

       return {
           ...super.getReceiptHeaderData(...arguments),
           partner: this.get_order().get_partner(),
           default_code: product ? product.default_code : null,
           order_date: orderDate,
           order_time: orderTime,
           pos_reference: order.name,
           config_name: this.config.name,

       };
   },
    /**
    getReceiptHeaderData() {
       const order = this.get_order();
       const product = order.get_orderlines()?.[0]?.get_product(); // get the first product in orderlines
       return {
           ...super.getReceiptHeaderData(...arguments),
           partner: this.get_order().get_partner(),
           default_code: product ? product.default_code : null,
       };
   },
        **/
});
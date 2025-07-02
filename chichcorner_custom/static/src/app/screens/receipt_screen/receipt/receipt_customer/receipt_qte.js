/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";

patch(Order.prototype, {
       setup(){
       super.setup(...arguments);
       },
        export_for_printing() {
        const result = super.export_for_printing(...arguments);

        let sum = 0;
        let unique_items = new Set(); // Set to store unique product IDs

        this.orderlines.forEach(function(line) {
            // Ensure the line is not a promotion or discount-only line
            if (!line.is_reward_line) {
                sum += line.quantity;
                unique_items.add(line.product.id); // Store unique product ID
            }
        });

        result.sum = sum;
        result.unique_items_count = unique_items.size; // Count unique products

        console.log("Total Quantity:", result.sum);
        console.log("Total Unique Items:", result.unique_items_count);
        return result;
    }
    /*
       export_for_printing() {
           const result = super.export_for_printing(...arguments);
          result.count = this.orderlines.length
          this.receipt = result.count
          var sum = 0;
          this.orderlines.forEach(function(t) {
                    sum += t.quantity;
                })
                result.sum = sum
        console.log('Exporting order:', result);
        return result;
       }

     */

});


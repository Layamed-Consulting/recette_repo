/** @odoo-module */
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

const originalGetLoyaltyPoints = Order.prototype.getLoyaltyPoints;

patch(Order.prototype, {
     setup(_defaultObj, options) {
           super.setup(...arguments);
           this.suggestion = this.suggestion || null;
       },
     init_from_JSON(json) {
      this.set_customer_suggestion(json.suggestion);
      super.init_from_JSON(...arguments);
   },
   export_as_JSON() {
       const json = super.export_as_JSON(...arguments);
       if (json) {
           json.suggestion = this.Suggestion;
       }
       return json;
   },
    set_customer_suggestion(suggestion) {
       this.Suggestion = suggestion;
   },
    get_customer_suggestion() {
        return this.suggestion;
    },
    getLoyaltyPoints() {

        // Call original method:
        const points = originalGetLoyaltyPoints.apply(this, arguments);

        const partner = this.get_partner();
        if (!partner) {
            return points;
        }

        const categoryIds = partner.category_id || [];
        const categoryNames = categoryIds.map(catId => {
            const category = this.pos.partner_categories.find(c => c.id === catId);
            return category ? category.display_name : '';
        });

        if (!categoryNames.includes('FID')) {
            return [];
        }

        return points;
    }
});

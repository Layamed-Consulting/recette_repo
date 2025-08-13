/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { RewardButton } from "@pos_loyalty/app/control_buttons/reward_button/reward_button";

patch(RewardButton.prototype, {
    _isDisabled() {
        const order = this.pos.get_order();
        const client = order?.get_partner();

        // If no client selected, do not disable the button 07/08/2025
        if (!client) return false;

        // Get category IDs
        const categoryIds = client.category_id;
        let categoryNames = [];

        if (categoryIds && categoryIds.length > 0) {
            // Get category names from loaded categories
            categoryNames = categoryIds.map(categoryId => {
                const categoryData = this.pos.partner_categories?.find(cat => cat.id === categoryId);
                return categoryData ? categoryData.display_name : "";
            });
        }

        // Disable the button if any of the client's categories is "NOTVIP"
        const isDisabled = !categoryNames.includes("FID");

        console.log("[LOYALTY] Client:", client.name, "| Categories:", categoryNames.join(", "), "| Reward button disabled:", isDisabled);

        return isDisabled;
    },

    hasClaimableRewards() {
        return !this._isDisabled() && this._getPotentialRewards().length > 0;
    },
});

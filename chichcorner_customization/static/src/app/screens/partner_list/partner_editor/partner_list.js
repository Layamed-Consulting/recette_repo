/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";

patch(PartnerDetailsEdit.prototype, {
    setup() {
        super.setup();
        // Add category_id to the changes state
        const partner = this.props.partner;
        // Store all existing categories as an array of IDs
        this.changes.category_id = partner.category_id ? partner.category_id.map(cat => cat[0] || cat) : [];
    },

    // Method to add a category
    addCategory(categoryId) {
        if (categoryId && !this.changes.category_id.includes(parseInt(categoryId))) {
            this.changes.category_id.push(parseInt(categoryId));
        }
    },

    // Method to remove a category
    removeCategory(categoryId) {
        const index = this.changes.category_id.indexOf(parseInt(categoryId));
        if (index > -1) {
            this.changes.category_id.splice(index, 1);
        }
    },

    // Method to toggle a category (add if not present, remove if present)
    toggleCategory(categoryId) {
        const id = parseInt(categoryId);
        if (this.changes.category_id.includes(id)) {
            this.removeCategory(id);
        } else {
            this.addCategory(id);
        }
    },

    // Check if a category is selected
    isCategorySelected(categoryId) {
        return this.changes.category_id.includes(parseInt(categoryId));
    },

    // Override saveChanges to add category_id handling
    saveChanges() {
        const processedChanges = {};
        for (const [key, value] of Object.entries(this.changes)) {
            if (key === 'category_id') {
                // Handle Many2many field - keep all selected categories
                if (Array.isArray(value) && value.length > 0) {
                    processedChanges[key] = [[6, 0, value]]; // Replace with all selected categories
                } else {
                    processedChanges[key] = [[5]]; // Clear all categories
                }
            } else if (this.intFields.includes(key)) {
                processedChanges[key] = parseInt(value) || false;
            } else {
                processedChanges[key] = value;
            }
        }
        if (
            processedChanges.state_id &&
            this.pos.states.find((state) => state.id === processedChanges.state_id)
                .country_id[0] !== processedChanges.country_id
        ) {
            processedChanges.state_id = false;
        }

        if ((!this.props.partner.name && !processedChanges.name) || processedChanges.name === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Customer Name Is Required"),
            });
        }
        processedChanges.id = this.props.partner.id || false;
        this.props.saveChanges(processedChanges);
    }
});
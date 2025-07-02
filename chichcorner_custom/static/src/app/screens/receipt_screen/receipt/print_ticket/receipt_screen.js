/** @odoo-module */
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
        this.printer = useService("printer");
    },
    async printGiftReceipt() {
        try {
            const order = this.pos.get_order();
            if (!order) {
                throw new Error('No active order found');
            }

            const receiptData = order.export_for_printing();
            const giftReceiptData = { ...receiptData };

            // Modify orderlines to hide prices
            giftReceiptData.orderlines = receiptData.orderlines.map(line => ({
                ...line,
                quantity: Number(line.quantity) || 0,
                unit_name: line.unit_name || '',
                product_name: line.product_name || '',
                price: 0,
                unitPrice: 0,
                price_display: 0,
                price_with_tax: 0,
                price_without_tax: 0,
                tax: 0,
                discount: Number(line.discount) || 0
            }));

            // Fields that should be empty arrays
            const arrayFields = [
                'paymentlines',
                'tax_details'
            ];

            arrayFields.forEach(field => {
                giftReceiptData[field] = [];
            });

            // Fields that should be zero values (not empty strings!)
            const zeroValueFields = [
                'total_paid',
                'amount',
                'change',
                'amount_total',
                'unitPrice',
                'amount_tax',
                'total_without_tax',
                'subtotal',
                'tax',
                'total'
            ];

            zeroValueFields.forEach(field => {
                giftReceiptData[field] = 0;
            });

            // Mark as gift receipt
            giftReceiptData.is_gift_receipt = true;


            // Add a title for the gift receipt
            giftReceiptData.receipt_type = "Gift Receipt";

            // Create a custom formatCurrency function to handle gift receipt
            const originalFormatCurrency = this.env.utils.formatCurrency;
            const giftFormatCurrency = (value) => {
                // For gift receipts, we'll hide all currency values with dashes
                if (giftReceiptData.is_gift_receipt && value === 0) {
                    return "---";
                }
                // Otherwise use the normal formatter
                return originalFormatCurrency(value);
            };

            await this.printer.print(
                OrderReceipt, {
                    data: giftReceiptData,
                    formatCurrency: giftFormatCurrency, // Use our custom formatter
                },
                { webPrintFallback: true }
            );

            console.log("Gift receipt printed successfully");

        } catch (error) {
            console.error("Error in printGiftReceipt:", error);
        }
    }
});
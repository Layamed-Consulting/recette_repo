/** @odoo-module **/

import { ClosePosPopup } from "@point_of_sale/app/navbar/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConnectionLostError } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

patch(ClosePosPopup.prototype, {
    async closeSession() {
        try {
            const sessionId = this.pos.pos_session.id;
            const notes = this.state.notes || "";
            const cashierName = this.pos.cashier.name || "";
            const storeName = this.pos.config.name;
            const cashDetails = this.props.default_cash_details;
            const cashExpected = parseFloat(cashDetails.amount || "0");
            const cashCounted = parseFloat(this.state.payments[cashDetails.id]?.counted || "0");
        //const cashDifference = this.getDifference();
            const cashDifference = cashCounted - cashExpected;

            const paymentMethodsData = [
                {
                    session_id: sessionId,
                    payment_method_id: cashDetails.id,
                    cashier_name: cashierName,
                    store_name: storeName,
                    payment_method_name: cashDetails.name,
                    expected: cashExpected,
                    counted_cash: cashCounted,
                    payment_differences: cashDifference,
                    notes: notes,
                },
                ...this.props.other_payment_methods.map(paymentMethod => {
                    const expected = parseFloat(paymentMethod.amount || 0);
                    const counted = parseFloat(this.state.payments[paymentMethod.id]?.counted || 0);
                    const difference =  counted - expected;

                    return {
                        session_id: sessionId,
                        payment_method_id: paymentMethod.id,
                        cashier_name: cashierName,
                        store_name: storeName,
                        payment_method_name: paymentMethod.name,
                        expected: expected,
                        counted_cash: counted,
                        payment_differences: difference,
                        notes: notes,
                    };
                }),
            ];
            for (const paymentMethodData of paymentMethodsData) {
                await this.orm.call("transaction.session", "create", [paymentMethodData]);
                console.log("Transaction session data saved successfully:", paymentMethodData);
            }
            await this.orm.call("pos.session", "close_session_from_ui", [
                sessionId,
                this.props.other_payment_methods.map((pm) => [
                    pm?.id || 0,
                    this.getDifference(pm?.id),
                ]),
            ]);
            window.location = "/web#action=point_of_sale.action_client_pos_menu";
        } catch (error) {
            await this.showErrorAndClose(error, _t("An error occurred while closing the session."));
            window.location = "/web#action=point_of_sale.action_client_pos_menu";
        }
    },

    async showErrorAndClose(error, customMessage) {
        const sessionid = this.pos.pos_session.id;
        console.error(customMessage, error);
        await this.popup.add(ErrorPopup, {
            title: _t("Session peut pas enregistrer"),
            body: _t(
                "Impossible d'enregistrer cette session.\n" +
                "You will be redirected to the back-end to manually close the session."
            ),
        });
        await this.orm.call("pos.session", "close_session_from_ui", [
                sessionid,
                this.props.other_payment_methods.map((pm) => [
                    pm?.id || 0,
                    0,
                ]),
            ]);
        window.location = "/web#action=point_of_sale.action_client_pos_menu";

    },
});
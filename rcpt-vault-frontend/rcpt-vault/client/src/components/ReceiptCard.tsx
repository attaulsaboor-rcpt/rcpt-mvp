import { type VaultReceipt } from "@shared/schema";
import { ChevronRight, ReceiptText } from "lucide-react";
import { getMerchantAvatarBg, getMerchantInitials } from "@/lib/format";

function formatAmount(pkr: number): string {
  return new Intl.NumberFormat("en-PK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(pkr);
}

function formatWhen(when: string): string {
  try {
    const d = new Date(when);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return when;
  }
}

interface ReceiptCardProps {
  receipt: VaultReceipt;
  onClick: (receipt: VaultReceipt) => void;
}

export function ReceiptCard({ receipt, onClick }: ReceiptCardProps) {
  const initials = getMerchantInitials(receipt.merchant_id);
  const bg = getMerchantAvatarBg();

  return (
    <button
      className="w-full text-left bg-card border border-card-border rounded-xl p-4 hover-elevate active-elevate-2 cursor-pointer transition-all duration-150"
      onClick={() => onClick(receipt)}
      data-testid={`card-receipt-${receipt.id}`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-11 h-11 ${bg} rounded-xl flex items-center justify-center text-white font-bold text-sm flex-shrink-0`}
          aria-label={receipt.merchant_id}
        >
          {initials}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p
                className="font-semibold text-foreground text-sm leading-tight truncate"
                data-testid={`text-merchant-${receipt.id}`}
              >
                {receipt.merchant_id}
              </p>
              <p
                className="text-xs text-muted-foreground mt-0.5"
                data-testid={`text-date-${receipt.id}`}
              >
                {formatWhen(receipt.when)}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1 flex-shrink-0">
              <span
                className="font-bold text-foreground text-base leading-tight tabular-nums"
                data-testid={`text-total-${receipt.id}`}
              >
                {formatAmount(receipt.total_pkr)}
              </span>
              <span className="text-xs text-muted-foreground">{receipt.source}</span>
            </div>
          </div>
        </div>

        <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
      </div>
    </button>
  );
}

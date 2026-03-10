import { useQuery } from "@tanstack/react-query";
import { useLocation, useParams } from "wouter";
import { type ReceiptDetail } from "@shared/schema";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  Share2,
  Download,
  Hash,
  Clock,
  CalendarDays,
  CheckCircle,
  CreditCard,
  User,
  Mail,
  Package,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fetchReceipt } from "@/lib/rcptApi";
import { getMerchantAvatarBg, getMerchantInitials } from "@/lib/format";

function formatAmount(value: number | null | undefined, currency?: string | null): string {
  if (value == null) return "—";
  const cur = currency ?? "PKR";
  try {
    return new Intl.NumberFormat("en-PK", {
      style: "currency",
      currency: cur,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${cur} ${value.toFixed(2)}`;
  }
}

function formatDateStr(str: string | null | undefined): string {
  if (!str) return "—";
  try {
    return new Date(str).toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return str;
  }
}

function formatTimeStr(str: string | null | undefined): string {
  if (!str) return "—";
  try {
    return new Date(str).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function StatusPill({ status }: { status?: string | null }) {
  if (!status) return null;
  const s = status.toLowerCase();
  const styles =
    s === "claimed"
      ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
      : s === "unclaimed"
      ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
      : "bg-muted text-muted-foreground";
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${styles}`}>
      {status}
    </span>
  );
}

export default function ReceiptDetailPage() {
  const params = useParams<{ id: string }>();
  const [, navigate] = useLocation();
  const { toast } = useToast();

  const receiptId = Number(params.id);

  const { data: receipt, isLoading, isError } = useQuery<ReceiptDetail>({
    queryKey: ["receipt", receiptId],
    queryFn: () => fetchReceipt(receiptId),
    enabled: !!receiptId && !isNaN(receiptId),
  });

  const primaryDate = receipt?.created_at ?? receipt?.date ?? receipt?.paid_at ?? null;
  const currency = receipt?.currency ?? "PKR";
  const hasItems = (receipt?.items?.length ?? 0) > 0;
  const hasBreakdown =
    receipt?.subtotal != null || receipt?.tax != null || receipt?.discount != null;

  function handleShare() {
    if (navigator.share) {
      navigator.share({
        title: `Receipt from ${receipt?.merchant_id}`,
        text: `${receipt?.merchant_id} · ${formatAmount(receipt?.total, currency)}`,
        url: window.location.href,
      });
    } else {
      navigator.clipboard.writeText(window.location.href);
      toast({ title: "Link copied", description: "Receipt link copied to clipboard." });
    }
  }

  function handleDownload() {
    toast({ title: "Downloading...", description: "Receipt PDF download coming soon." });
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background" data-testid="receipt-detail-loading">
        <div className="max-w-lg mx-auto px-4 pt-6 pb-24">
          <div className="flex items-center gap-3 mb-6">
            <Skeleton className="w-9 h-9 rounded-lg" />
            <Skeleton className="h-5 w-32" />
          </div>
          <div className="bg-card border border-card-border rounded-2xl p-6 space-y-5">
            <div className="flex items-center gap-4">
              <Skeleton className="w-16 h-16 rounded-xl" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-20" />
              </div>
            </div>
            <Skeleton className="h-px w-full" />
            <div className="text-center space-y-2">
              <Skeleton className="h-10 w-40 mx-auto" />
              <Skeleton className="h-4 w-28 mx-auto" />
            </div>
            <Skeleton className="h-px w-full" />
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex justify-between">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isError || !receipt) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center px-6">
          <p className="text-foreground font-semibold mb-2">Receipt not found</p>
          <p className="text-muted-foreground text-sm mb-4">
            This receipt may have expired or been removed.
          </p>
          <Button onClick={() => navigate("/")}>Back to Vault</Button>
        </div>
      </div>
    );
  }

  const initials = getMerchantInitials(receipt.merchant_id);
  const bg = getMerchantAvatarBg();

  return (
    <div className="min-h-screen bg-background" data-testid="receipt-detail-page">
      <div className="max-w-lg mx-auto px-4 pt-6 pb-24">

        {/* Back nav */}
        <div className="flex items-center justify-between mb-6">
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 -ml-2"
            onClick={() => navigate("/")}
            data-testid="button-back"
          >
            <ArrowLeft className="w-4 h-4" />
            Vault
          </Button>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={handleShare}
              data-testid="button-share"
            >
              <Share2 className="w-3.5 h-3.5" />
              Share
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={handleDownload}
              data-testid="button-download"
            >
              <Download className="w-3.5 h-3.5" />
              Save
            </Button>
          </div>
        </div>

        {/* Receipt card */}
        <div
          className="bg-card border border-card-border rounded-2xl overflow-hidden"
          data-testid="receipt-card-detail"
        >
          {/* Merchant header */}
          <div className="px-6 pt-6 pb-5">
            <div className="flex items-center gap-4 mb-4">
              <div
                className={`w-16 h-16 ${bg} rounded-xl flex items-center justify-center text-white font-bold text-xl flex-shrink-0`}
              >
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <h1
                  className="font-bold text-xl text-foreground leading-tight truncate"
                  data-testid="text-receipt-merchant"
                >
                  {receipt.merchant_id}
                </h1>
                <div className="flex items-center gap-2 mt-1">
                  <StatusPill status={receipt.status} />
                  {!receipt.status && receipt.terminal_id && (
                    <span className="text-xs text-muted-foreground font-mono truncate">
                      {receipt.terminal_id}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Hero total */}
            <div className="text-center py-3">
              <p
                className="text-4xl font-bold text-foreground tabular-nums"
                data-testid="text-receipt-total"
              >
                {formatAmount(receipt.total, currency)}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {formatDateStr(primaryDate)}
              </p>
            </div>
          </div>

          <Separator />

          {/* Meta grid */}
          <div className="px-6 py-4 grid grid-cols-2 gap-y-4">
            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 bg-muted rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <CalendarDays className="w-3.5 h-3.5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Date</p>
                <p className="text-sm font-medium text-foreground">{formatDateStr(primaryDate)}</p>
              </div>
            </div>

            <div className="flex items-start gap-2.5">
              <div className="w-7 h-7 bg-muted rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <Clock className="w-3.5 h-3.5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Time</p>
                <p className="text-sm font-medium text-foreground">{formatTimeStr(primaryDate)}</p>
              </div>
            </div>

            <div className="flex items-start gap-2.5 col-span-2">
              <div className="w-7 h-7 bg-muted rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <Hash className="w-3.5 h-3.5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Receipt ID</p>
                <p className="text-sm font-medium text-foreground font-mono">#{receipt.id}</p>
              </div>
            </div>

            {receipt.cashier && (
              <div className="flex items-start gap-2.5 col-span-2">
                <div className="w-7 h-7 bg-muted rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Cashier</p>
                  <p className="text-sm font-medium text-foreground">{receipt.cashier}</p>
                </div>
              </div>
            )}

            {receipt.paymentMethod && (
              <div className="flex items-start gap-2.5 col-span-2">
                <div className="w-7 h-7 bg-muted rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                  <CreditCard className="w-3.5 h-3.5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Payment</p>
                  <p className="text-sm font-medium text-foreground">{receipt.paymentMethod}</p>
                </div>
              </div>
            )}

            {receipt.email && (
              <div className="flex items-start gap-2.5 col-span-2">
                <div className="w-7 h-7 bg-muted rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Mail className="w-3.5 h-3.5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Email</p>
                  <p className="text-sm font-medium text-foreground truncate">{receipt.email}</p>
                </div>
              </div>
            )}
          </div>

          {/* Items table */}
          {hasItems && (
            <>
              <Separator />
              <div className="px-6 py-4">
                <div className="flex items-center gap-2 mb-3">
                  <Package className="w-3.5 h-3.5 text-muted-foreground" />
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    Items
                  </p>
                </div>
                <div className="space-y-2.5">
                  {receipt.items!.map((item, i) => (
                    <div key={i} className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p
                          className="text-sm font-medium text-foreground leading-tight"
                          data-testid={`text-item-name-${i}`}
                        >
                          {item.name}
                        </p>
                        {item.unitPrice != null && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {formatAmount(item.unitPrice, currency)} × {item.qty}
                          </p>
                        )}
                        {item.unitPrice == null && item.qty > 1 && (
                          <p className="text-xs text-muted-foreground mt-0.5">qty {item.qty}</p>
                        )}
                      </div>
                      <span
                        className="text-sm font-semibold text-foreground tabular-nums flex-shrink-0"
                        data-testid={`text-item-price-${i}`}
                      >
                        {formatAmount(item.linePrice, currency)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Totals breakdown */}
          {hasBreakdown && (
            <>
              <Separator />
              <div className="px-6 py-4 space-y-2">
                {receipt.subtotal != null && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Subtotal</span>
                    <span className="text-foreground tabular-nums">
                      {formatAmount(receipt.subtotal, currency)}
                    </span>
                  </div>
                )}
                {receipt.discount != null && receipt.discount > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Discount</span>
                    <span className="text-green-600 dark:text-green-400 tabular-nums">
                      −{formatAmount(receipt.discount, currency)}
                    </span>
                  </div>
                )}
                {receipt.tax != null && receipt.tax > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Tax</span>
                    <span className="text-foreground tabular-nums">
                      {formatAmount(receipt.tax, currency)}
                    </span>
                  </div>
                )}
              </div>
            </>
          )}

          <Separator />

          {/* Total row */}
          <div className="px-6 py-4">
            <div className="flex justify-between items-center">
              <span className="font-bold text-foreground">Total</span>
              <span
                className="font-bold text-foreground text-lg tabular-nums"
                data-testid="text-receipt-total-row"
              >
                {formatAmount(receipt.total, currency)}
              </span>
            </div>
          </div>

          {/* Verified watermark */}
          <div className="mx-6 mb-6 mt-1 bg-primary/5 border border-primary/10 rounded-xl p-3 flex items-center gap-3">
            <CheckCircle className="w-4 h-4 text-primary flex-shrink-0" />
            <div>
              <p className="text-xs font-semibold text-primary">Verified Digital Receipt</p>
              <p className="text-xs text-muted-foreground">
                Powered by RCPT · {formatDateStr(primaryDate)}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

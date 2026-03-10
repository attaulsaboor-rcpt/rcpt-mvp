export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr.replace(" ", "T"));
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr.replace(" ", "T"));
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTime(dateStr: string): string {
  const d = new Date(dateStr.replace(" ", "T"));
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

const MERCHANT_COLORS: Record<string, string> = {
  "Food & Drink": "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  "Grocery": "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  "Electronics": "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  "Health": "bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400",
  "Retail": "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
};

const MERCHANT_BG: Record<string, string> = {
  "Food & Drink": "bg-orange-500",
  "Grocery": "bg-green-600",
  "Electronics": "bg-blue-600",
  "Health": "bg-pink-500",
  "Retail": "bg-purple-600",
};

export function getMerchantCategoryStyle(category?: string): string {
  return MERCHANT_COLORS[category || ""] || "bg-muted text-muted-foreground";
}

export function getMerchantAvatarBg(category?: string): string {
  return MERCHANT_BG[category || ""] || "bg-primary";
}

export function getMerchantInitials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

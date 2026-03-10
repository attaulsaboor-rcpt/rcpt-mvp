import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { type VaultReceipt } from "@shared/schema";
import { getDeviceId } from "@/lib/deviceId";
import { fetchVault } from "@/lib/rcptApi";
import { ReceiptCard } from "@/components/ReceiptCard";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Search,
  Nfc,
  X,
  ArrowDownAZ,
  ChevronDown,
} from "lucide-react";
import { useLocation } from "wouter";

type SortOption = "newest" | "oldest" | "highest" | "lowest";
type FilterMerchant = string | "all";

const SORT_LABELS: Record<SortOption, string> = {
  newest: "Newest first",
  oldest: "Oldest first",
  highest: "Highest amount",
  lowest: "Lowest amount",
};

function formatAmount(pkr: number): string {
  return new Intl.NumberFormat("en-PK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(pkr);
}

export default function VaultPage() {
  const [, navigate] = useLocation();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortOption>("newest");
  const [filterMerchant, setFilterMerchant] = useState<FilterMerchant>("all");

  const deviceId = getDeviceId();

  const { data: receipts, isLoading } = useQuery<VaultReceipt[]>({
    queryKey: ["vault", deviceId],
    queryFn: () => fetchVault(deviceId),
  });

  const merchants = useMemo(() => {
    if (!receipts) return [];
    return Array.from(new Set(receipts.map((r) => r.merchant_id))).sort();
  }, [receipts]);

  const filtered = useMemo(() => {
    if (!receipts) return [];
    let list = [...receipts];

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((r) => r.merchant_id.toLowerCase().includes(q));
    }

    if (filterMerchant !== "all") {
      list = list.filter((r) => r.merchant_id === filterMerchant);
    }

    switch (sort) {
      case "newest":
        list.sort((a, b) => (a.when < b.when ? 1 : -1));
        break;
      case "oldest":
        list.sort((a, b) => (a.when > b.when ? 1 : -1));
        break;
      case "highest":
        list.sort((a, b) => b.total_pkr - a.total_pkr);
        break;
      case "lowest":
        list.sort((a, b) => a.total_pkr - b.total_pkr);
        break;
    }

    return list;
  }, [receipts, search, sort, filterMerchant]);

  const totalSpend = useMemo(
    () => filtered.reduce((sum, r) => sum + r.total_pkr, 0),
    [filtered]
  );

  function handleReceiptClick(receipt: VaultReceipt) {
    navigate(`/receipt/${receipt.id}`);
  }

  function handleTap() {
    navigate("/t/term_demo_001");
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-lg mx-auto px-4 pt-8 pb-24">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-1">
              RCPT Vault
            </p>
            <h1 className="text-2xl font-bold text-foreground">My Receipts</h1>
            {!isLoading && filtered.length > 0 && (
              <p className="text-sm text-muted-foreground mt-0.5">
                {filtered.length} receipt{filtered.length !== 1 ? "s" : ""} ·{" "}
                {formatAmount(totalSpend)} total
              </p>
            )}
          </div>
          <Button
            size="sm"
            className="gap-1.5 mt-1"
            onClick={handleTap}
            data-testid="button-simulate-nfc"
          >
            <Nfc className="w-4 h-4" />
            Tap
          </Button>
        </div>

        {/* Search + Filters */}
        <div className="space-y-2.5 mb-5">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
            <Input
              type="search"
              placeholder="Search by merchant..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-9 bg-card border-card-border"
              data-testid="input-search"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                data-testid="button-clear-search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="flex gap-2">
            {/* Merchant filter */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5 flex-1 justify-between"
                  data-testid="button-filter-merchant"
                >
                  <span className="truncate">
                    {filterMerchant === "all" ? "All Merchants" : filterMerchant}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56">
                <DropdownMenuRadioGroup
                  value={filterMerchant}
                  onValueChange={setFilterMerchant}
                >
                  <DropdownMenuRadioItem value="all" data-testid="filter-all">
                    All Merchants
                  </DropdownMenuRadioItem>
                  {merchants.map((m) => (
                    <DropdownMenuRadioItem
                      key={m}
                      value={m}
                      data-testid={`filter-merchant-${m}`}
                    >
                      {m}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Sort */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5 flex-shrink-0"
                  data-testid="button-sort"
                >
                  <ArrowDownAZ className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">{SORT_LABELS[sort]}</span>
                  <span className="sm:hidden">Sort</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuRadioGroup
                  value={sort}
                  onValueChange={(v) => setSort(v as SortOption)}
                >
                  {Object.entries(SORT_LABELS).map(([value, label]) => (
                    <DropdownMenuRadioItem
                      key={value}
                      value={value}
                      data-testid={`sort-${value}`}
                    >
                      {label}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {(search || filterMerchant !== "all") && (
            <div className="flex items-center gap-2 flex-wrap">
              {search && (
                <span className="inline-flex items-center gap-1 bg-primary/10 text-primary text-xs rounded-full px-2.5 py-1 font-medium">
                  "{search}"
                  <button onClick={() => setSearch("")}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {filterMerchant !== "all" && (
                <span className="inline-flex items-center gap-1 bg-primary/10 text-primary text-xs rounded-full px-2.5 py-1 font-medium">
                  {filterMerchant}
                  <button onClick={() => setFilterMerchant("all")}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Receipt List */}
        {isLoading ? (
          <div className="space-y-3" data-testid="skeleton-list">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="bg-card border border-card-border rounded-xl p-4"
              >
                <div className="flex items-center gap-3">
                  <Skeleton className="w-11 h-11 rounded-xl flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="flex justify-between">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-5 w-16" />
                    </div>
                    <Skeleton className="h-3 w-24" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 && !search && filterMerchant === "all" ? (
          <EmptyState onSimulate={handleTap} />
        ) : filtered.length === 0 ? (
          <div className="text-center py-16" data-testid="no-results">
            <p className="text-muted-foreground text-sm">
              No receipts match your search.
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="mt-3"
              onClick={() => {
                setSearch("");
                setFilterMerchant("all");
              }}
            >
              Clear filters
            </Button>
          </div>
        ) : (
          <div className="space-y-3" data-testid="receipt-list">
            {filtered.map((receipt) => (
              <ReceiptCard
                key={receipt.id}
                receipt={receipt}
                onClick={handleReceiptClick}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

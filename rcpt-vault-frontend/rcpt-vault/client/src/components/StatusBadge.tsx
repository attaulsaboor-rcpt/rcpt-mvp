import { Badge } from "@/components/ui/badge";
import { CheckCircle, Clock, XCircle } from "lucide-react";

type Status = "CLAIMED" | "UNCLAIMED" | "EXPIRED";

const STATUS_CONFIG: Record<Status, { label: string; icon: typeof CheckCircle; classes: string }> = {
  CLAIMED: {
    label: "Claimed",
    icon: CheckCircle,
    classes: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
  UNCLAIMED: {
    label: "Unclaimed",
    icon: Clock,
    classes: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  },
  EXPIRED: {
    label: "Expired",
    icon: XCircle,
    classes: "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400",
  },
};

interface StatusBadgeProps {
  status: Status;
  size?: "sm" | "default";
}

export function StatusBadge({ status, size = "default" }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.UNCLAIMED;
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium no-default-active-elevate ${config.classes}`}
      data-testid={`status-badge-${status.toLowerCase()}`}
    >
      <Icon className="w-3 h-3 flex-shrink-0" />
      {config.label}
    </span>
  );
}

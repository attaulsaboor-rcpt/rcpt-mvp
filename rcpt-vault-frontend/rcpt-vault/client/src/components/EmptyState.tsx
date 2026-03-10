import { Button } from "@/components/ui/button";
import { Wallet, Nfc } from "lucide-react";

interface EmptyStateProps {
  onSimulate: () => void;
}

export function EmptyState({ onSimulate }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 text-center" data-testid="empty-state">
      <div className="w-20 h-20 bg-primary/10 rounded-2xl flex items-center justify-center mb-6">
        <Wallet className="w-10 h-10 text-primary" />
      </div>

      <h2 className="text-xl font-bold text-foreground mb-2">
        Your vault is empty
      </h2>
      <p className="text-muted-foreground text-sm max-w-xs leading-relaxed mb-2">
        You have no receipts yet.
      </p>
      <p className="text-muted-foreground text-sm max-w-xs leading-relaxed mb-8">
        Tap an RCPT tag after checkout to receive your digital receipt instantly.
      </p>

      <div className="flex flex-col items-center gap-3 w-full max-w-xs">
        <Button
          onClick={onSimulate}
          className="w-full gap-2"
          data-testid="button-simulate-empty"
        >
          <Nfc className="w-4 h-4" />
          Simulate NFC Tap
        </Button>
        <p className="text-xs text-muted-foreground">
          Demo mode — try the claim flow
        </p>
      </div>
    </div>
  );
}

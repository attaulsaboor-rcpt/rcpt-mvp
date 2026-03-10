import { useEffect, useState } from "react";
import { useParams, useLocation } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { claimReceipt, type ClaimResponse } from "@/lib/rcptApi";
import { getDeviceId } from "@/lib/deviceId";
import {
  Nfc,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ReceiptText,
} from "lucide-react";

type ClaimStep = "connecting" | "claiming" | "success" | "error";

export default function TerminalClaimPage() {
  const params = useParams<{ terminalId: string }>();
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<ClaimStep>("connecting");
  const [claimResult, setClaimResult] = useState<ClaimResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");

  const terminalId = params.terminalId;
  const deviceId = getDeviceId();

  function runClaim() {
    setStep("claiming");
    claimReceipt(deviceId, terminalId)
      .then((result) => {
        setClaimResult(result);
        setStep("success");
        queryClient.invalidateQueries({ queryKey: ["vault", deviceId] });
      })
      .catch((err: Error) => {
        setErrorMessage(err.message || "Something went wrong. Please try again.");
        setStep("error");
      });
  }

  useEffect(() => {
    if (!terminalId) return;
    const timer = setTimeout(runClaim, 1600);
    return () => clearTimeout(timer);
  }, [terminalId]);

  function handleRetry() {
    setStep("connecting");
    setErrorMessage("");
    setClaimResult(null);
    setTimeout(runClaim, 1600);
  }

  function handleGoToVault() {
    navigate("/");
  }

  return (
    <div
      className="min-h-screen bg-background flex flex-col items-center justify-center px-6"
      data-testid="terminal-claim-page"
    >
      {/* Branding */}
      <div className="mb-10 text-center">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
          RCPT Vault
        </p>
      </div>

      <div className="w-full max-w-sm">

        {/* CONNECTING */}
        {step === "connecting" && (
          <div className="flex flex-col items-center text-center gap-6" data-testid="step-connecting">
            <div className="relative w-28 h-28">
              <div className="absolute inset-0 bg-primary/10 rounded-full animate-ping opacity-50" />
              <div
                className="absolute inset-2 bg-primary/10 rounded-full animate-ping opacity-30"
                style={{ animationDelay: "0.3s" }}
              />
              <div className="relative w-28 h-28 bg-primary/15 rounded-full flex items-center justify-center">
                <Nfc className="text-primary animate-pulse" style={{ width: 52, height: 52 }} />
              </div>
            </div>
            <div className="space-y-1.5">
              <p className="text-xl font-bold text-foreground">Connecting to terminal</p>
              <p className="text-sm text-muted-foreground">
                Reading receipt from{" "}
                <span className="font-medium text-foreground font-mono">{terminalId}</span>
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <div className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" />
              <span>Establishing secure connection...</span>
            </div>
          </div>
        )}

        {/* CLAIMING */}
        {step === "claiming" && (
          <div className="flex flex-col items-center text-center gap-6" data-testid="step-claiming">
            <div className="w-24 h-24 bg-primary/10 rounded-2xl flex items-center justify-center">
              <Loader2 className="text-primary animate-spin" style={{ width: 48, height: 48 }} />
            </div>
            <div className="space-y-1.5">
              <p className="text-xl font-bold text-foreground">Claiming receipt...</p>
              <p className="text-sm text-muted-foreground">Adding to your vault</p>
            </div>
          </div>
        )}

        {/* SUCCESS */}
        {step === "success" && (
          <div className="flex flex-col items-center text-center gap-6" data-testid="step-success">
            <div className="w-24 h-24 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
              <CheckCircle2
                className="text-green-600 dark:text-green-400"
                style={{ width: 48, height: 48 }}
              />
            </div>

            <div className="space-y-1.5">
              <p className="text-xl font-bold text-foreground">Receipt Claimed!</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {claimResult?.message || "Your receipt has been added to your vault."}
              </p>
            </div>

            {claimResult?.receipt_id && (
              <div className="w-full bg-card border border-card-border rounded-xl p-4 flex items-center gap-3">
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center flex-shrink-0">
                  <ReceiptText className="w-5 h-5 text-primary" />
                </div>
                <div className="text-left min-w-0 flex-1">
                  <p className="text-sm font-semibold text-foreground">
                    Receipt #{claimResult.receipt_id}
                  </p>
                  <p className="text-xs text-muted-foreground font-mono truncate">{terminalId}</p>
                </div>
                <div className="w-2 h-2 bg-green-500 rounded-full flex-shrink-0" />
              </div>
            )}

            <Button
              className="w-full gap-2"
              onClick={handleGoToVault}
              data-testid="button-go-to-vault"
            >
              View My Vault
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        )}

        {/* ERROR */}
        {step === "error" && (
          <div className="flex flex-col items-center text-center gap-6" data-testid="step-error">
            <div className="w-24 h-24 bg-destructive/10 rounded-full flex items-center justify-center">
              <AlertCircle
                className="text-destructive"
                style={{ width: 48, height: 48 }}
              />
            </div>

            <div className="space-y-1.5">
              <p className="text-xl font-bold text-foreground">Claim Failed</p>
              <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
                {errorMessage}
              </p>
            </div>

            <div className="flex flex-col gap-2 w-full">
              <Button
                className="w-full gap-2"
                onClick={handleRetry}
                data-testid="button-retry"
              >
                <Nfc className="w-4 h-4" />
                Try Again
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleGoToVault}
                data-testid="button-go-to-vault-error"
              >
                Go to Vault
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Terminal badge */}
      <div className="mt-12 flex items-center gap-2 text-xs text-muted-foreground">
        <Nfc className="w-3.5 h-3.5" />
        <span>
          Terminal:{" "}
          <span className="font-mono font-medium text-foreground">{terminalId}</span>
        </span>
      </div>
    </div>
  );
}

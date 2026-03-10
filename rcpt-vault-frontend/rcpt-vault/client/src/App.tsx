import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import VaultPage from "@/pages/VaultPage";
import ReceiptDetailPage from "@/pages/ReceiptDetailPage";
import TerminalClaimPage from "@/pages/TerminalClaimPage";
import NotFound from "@/pages/not-found";

function Router() {
  return (
    <Switch>
      <Route path="/" component={VaultPage} />
      <Route path="/receipt/:id" component={ReceiptDetailPage} />
      <Route path="/t/:terminalId" component={TerminalClaimPage} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Router />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;

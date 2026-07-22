import Link from "next/link";
import { Suspense } from "react";
import { ContextKernelDemo } from "@/features/context-kernel/ContextKernelDemo";

export const metadata = {
  title: "Connect Sleeper — Razzle",
  description:
    "Pull scoring, rosters, and league truth for the Sleeper leagues you own.",
};

export default function ConnectPage() {
  return (
    <main style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <nav
        style={{
          display: "flex",
          gap: "16px",
          padding: "12px 24px",
          borderBottom: "2px dashed var(--ink-faint)",
        }}
      >
        <Link
          href="/"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            color: "var(--ink-medium)",
            textDecoration: "none",
          }}
        >
          ← Razzle
        </Link>
        <Link
          href="/scratchpad"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            color: "var(--ink-medium)",
            textDecoration: "none",
          }}
        >
          Scratchpad
        </Link>
      </nav>

      <Suspense
        fallback={
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "24px",
              color: "var(--ink-light)",
              padding: "48px 24px",
            }}
          >
            checking the tape...
          </p>
        }
      >
        <ContextKernelDemo />
      </Suspense>
    </main>
  );
}

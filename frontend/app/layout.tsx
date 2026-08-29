import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ProtocolForge — Agentic Assay Compiler",
  description:
    "Compiles unstructured lab protocols into a verified execution DAG and 96-well layout.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen scientific-grid-bg">{children}</body>
    </html>
  );
}

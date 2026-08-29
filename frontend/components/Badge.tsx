import { LucideIcon } from "lucide-react";
import React from "react";

type Tone = "success" | "warn" | "danger" | "neutral" | "accent";

const toneClasses: Record<Tone, string> = {
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  warn: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  danger: "bg-red-500/10 text-red-400 border-red-500/30",
  neutral: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  accent: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
};

export default function Badge({
  icon: Icon,
  children,
  tone = "neutral",
  title,
}: {
  icon?: LucideIcon;
  children: React.ReactNode;
  tone?: Tone;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-tight ${toneClasses[tone]}`}
    >
      {Icon ? <Icon size={11} strokeWidth={2.5} /> : null}
      {children}
    </span>
  );
}

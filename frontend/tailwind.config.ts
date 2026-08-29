import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        forge: {
          bg: "#0a0e14",
          panel: "#11161f",
          border: "#1f2937",
          accent: "#22d3ee",
          accent2: "#a78bfa",
          success: "#34d399",
          warn: "#fbbf24",
          danger: "#f87171",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
};
export default config;

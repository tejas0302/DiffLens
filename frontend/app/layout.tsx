import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "DiffLens",
  description: "Read pull requests by intent, not by file.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            <span className="brand-mark" aria-hidden /> DiffLens
          </Link>
          <span className="tagline">Read pull requests by intent, not by file.</span>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}

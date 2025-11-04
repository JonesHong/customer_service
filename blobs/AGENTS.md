# Repository Guidelines

## Project Structure & Module Organization
- `app/` hosts the Next.js App Router entry point; `layout.tsx` and `page.tsx` define the shell while `SplineViewer.tsx` drives the interactive scene.
- Domain logic lives under `app/utils/` (animations, audio, chat, LiveKit) with shared types in `app/types/`.
- Reuse LiveKit wiring through `app/hooks/useLiveKit.ts`; extend it rather than duplicating session logic.
- Runtime assets are served from `public/`; `assets/` and `samples/` store design references and should stay lightweight.

## Build, Test, and Development Commands
- `npm run dev` — start the local dev server at http://localhost:3000 with hot reload.
- `npm run build` — generate the production bundle; verify it before shipping.
- `npm run start` — serve the latest build for smoke testing.
- `npm run lint` — run Next.js ESLint rules; fix warnings before committing.

## Coding Style & Naming Conventions
- Favor TypeScript types and interfaces stored in `app/types`, especially for LiveKit and Spline APIs.
- Follow the repo’s Prettier-like formatting enforced by ESLint (2-space indent, double quotes in TSX, dangling commas where valid).
- Use PascalCase for components (`SplineViewer`), camelCase for functions/hooks (`useLiveKit`, `createAIMessage`), and keep CSS edits in `app/globals.css` scoped and class-based.

## Testing Guidelines
- Automated tests are not yet configured; create Jest + Testing Library suites under `app/**/__tests__` or `tests/` as you add coverage.
- Mock external services (LiveKit, Spline runtime) to keep tests deterministic.
- Before pushing, ensure `npm run lint` and `npm run build` succeed and document any manual QA steps for audio/chat flows.

## Commit & Pull Request Guidelines
- Use Conventional Commits with concise Traditional Chinese subjects, e.g., `feat: 新增 LiveKit 授權提示`.
- Reference related issues in the body and list commands executed during validation.
- Pull requests should summarize intent, include screenshots or updated `samples/` assets for UI tweaks, and call out configuration changes (.env requirements, LiveKit tokens).

## Asset & Configuration Notes
- Keep secrets out of version control; load LiveKit credentials via `.env.local` and update `next.config.js` cautiously.
- When adjusting module paths, revise `tsconfig.json` paths and verify imports inside `app/utils/**`.
- Optimize imagery before adding to `public/`; store large Spline exports in shared storage instead of git.

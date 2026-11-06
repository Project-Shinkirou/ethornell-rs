# Upstream integration

`shinki-upstream-3ee43dab` replays the Shinki adapter onto upstream `main` at
`3ee43dab43854e2f9c614dd1d26213e17911d877` (2026-11-05, `fix 0E`). The previous
integration base was `b5de417e4cff681bd2afb929e22e903d64602456`. The published
`shinki` branch remains at `f8362be7d2f4d634c25a98a317dfe56ffae56346`; its
history is not rewritten. The adapter uses Rust 1.98 and edition 2024.

The embedded frontend uses upstream's shared `frame_presenter` and refactored wgpu renderer, including gamma-space composition, text effects and frame budgets. Offscreen capture, explicit per-runtime fonts and encodings, host modal services, live child-thread completion and decoder-owned shutdown remain integrated.

Message wrapping, ruby spans, continued-page cursors and caret placement pass the selected runtime font through the upstream layout helpers. Embedded bootstrap supplies its display encoding to the new runtime constructor and leaves native clock-jump filtering to the engine, including clock-freeze sections.

## Replay record

The original adapter started at upstream `6550460beb2012781cdaffdf18da59780de422ef`.
Its integration merge `4671406df1ea61164862e2d1c7e139dac4dc5afb` incorporated
the previous base `b5de417e`; that base is also the merge base of the published
adapter and the previous upstream integration.

Directly replaying `d308520` conflicted in `.gitignore`, `Cargo.toml`,
`README.md`, `crates/ethornell-app/src/{host_dialog,lib,native_graph_sys92,snapshot,user_files,window}.rs`,
`crates/ethornell-audio/src/lib.rs`, `crates/ethornell-render/src/lib.rs` and
`crates/ethornell-vm/src/lib.rs`. That attempt was aborted. The manual replay
uses the already resolved adapter delta of `4671406` against its upstream
second parent (`cherry-pick -m 2`), preserving these five earlier commits
together with their integration resolutions:

- `d308520`: C ABI v3 adapter, offscreen rendering, host services, display
  localization, per-runtime fonts and session-owned audio shutdown.
- `dee3d09`: rename to `shinki-emu-ethornell-rs` and core build manifest.
- `f159d60`: pin the ShinkiEMU ABI/build helper.
- `24af94e`: accept Linux x64 GNU for the embedded adapter.
- `4671406`: adapt those hooks to upstream's shared compositor and renderer.

The manual replay conflicted only in `README.md`. The resolution keeps the
new upstream Claims section and its explicit display-encoding documentation,
removes stale auto-detection prose, and retains the adapter documentation with
the new branch and base. Upstream VM, archive, native call and resource fixes
from the new base remain intact; the adapter adds no title whitelist. The
upstream `DEFAULT_GAME_ID = "Tayutama2TV"` fallback is unchanged upstream code.

The remaining commits replayed individually and cleanly:

- `b42f0b5`: retain upstream restart dispatch.
- `32f56dd`: adapt current native frontend APIs.
- `0ce023b`: retain display settings on restart.
- `3275052`: pass fixture display encoding in the runtime regression.
- `61e63d9`: carry detected display encoding.
- `700d9ba`: Apple core integration and static query registration.
- `f8362be`: relocatable Mach-O install identities.

Save and configuration paths retain the upstream behavior; this replay adds
no managed save root or title-specific configuration.


# Native display localization

The Shinki ABI exposes three per-game fields:

- `text_encoding`: `cp932` (default) or `gbk`, applied only at native graph-text presentation boundaries through the existing VM graph-text decoding option.
- `font_path`: game-root-relative font file, empty by default to retain existing font selection. Declared with `CONFIG_FLAG_FILE_PATH | CONFIG_FLAG_GAME_RELATIVE`.
- `font_index`: zero-based SFNT/TTC face index, default `0`; a nonzero index requires an explicit font file. Declared as advanced with step `1`.

All fields carry Chinese labels, descriptions and groups (`语言`, `高级`); `text_encoding` choices are labelled `Shift-JIS（日文原版）` and `GBK（简体中文）`. The ABI v3 descriptor reports display name `ethornell-rs` and family name `Ethornell / BGI`.

The selected face is shared by GPU text rendering, CPU text composition, bitmap-text rasterization and glyph measurement. Missing files, invalid faces and missing required presentation glyphs fail explicitly instead of substituting a system font. Graph92 direct bitmap text uses the selected display encoding for byte-cell layout and glyph decoding.
Default CPU font discovery is lazy and owned by each runtime, replacing the process-global cache. The standalone native CLI's existing snapshot-font environment setting remains a default discovery input; an explicit ABI font overrides it. GPU default system-font discovery is unchanged.

Resource names, archive lookup/order, VM opcode decoding, internal string operations and choice/file targets keep their existing behavior. No archive decoder, protector runtime, Lua display hook or game-specific offset is added. Existing native archive and image readers continue to own standard resources, including BMP.

Public tests cover typed configuration/defaults, invalid font paths/faces, an original synthetic square-glyph SFNT fixture, selected-font CPU measurement/rasterization/coverage and GBK double-byte cells. Existing VM tests exercise GBK display decoding while preserving CP932 resource names and raw memory. These tests do not execute commercial games or protected binaries.

The HD external private-container consumer and additional archive ownership, and Sakura's protected private-resource consumer, remain separate conversion prerequisites. These display options do not establish complete localization support for either installation.

# Shinki adapter package

`crates/shinki-emu-ethornell-rs` is the ShinkiEMU C ABI v3 adapter: package `shinki-emu-ethornell-rs`, library `shinki_emu_ethornell_rs`, plugin id `ethornell-rs`. It exports `shinki_emu_query`; the `diagnostic-bridge` feature is used for the dynamically loaded `shinki_emu_ethornell_rs.dll`. Its ABI and host-side build helper use `Project-Shinkirou/ShinkiEMU@cb8d9dd22d7d0ab129085b324c94d6dc81fa19e3`. The Cargo build script writes the target/profile and license inputs to `core-build.json`; Cargo owns the actual Rust library build.

Core-side changes for embedding are the shared standalone/embedded composition, the offscreen embedded frontend, typed host dialogs, per-runtime font discovery and session-owned audio shutdown in `ethornell-app`, `ethornell-render` and `ethornell-audio`.

The adapter accepts both macOS architectures and the iOS device/simulator triples. Its `rlib` exposes the Rust-path `QUERY` for static registration without an unmangled export; `diagnostic-bridge` enables the dynamic `shinki_emu_query` symbol for the `cdylib`. License inputs stay in `core-build.json`.

# License text

`LICENSE-MPL-2.0` is the canonical Mozilla Public License 2.0 text, added to accompany the `MPL-2.0` declaration in the upstream root `[workspace.package]`. Upstream ships no license file.

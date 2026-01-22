Name:           arksigner-manager
Version:        1.0.0
Release:        1%{?dist}
Summary:        ArkSigner manager (GTK4 GUI + root CLI) with native+container modes
License:        GPL-3.0
BuildArch:      noarch
URL:            https://github.com/mfn77/Arksigner-Manager

Source0:        %{name}-%{version}.tar.gz

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       polkit
Requires:       systemd
Requires:       systemd-container
Requires:       pcsc-lite
Requires:       pcsc-lite-ccid
Requires:       opensc
Requires:       pcsc-tools
Requires:       debootstrap
Requires:       curl
Requires:       util-linux
Requires:       nss-tools
Requires:       binutils
Requires:       tar
Requires:       xz
Requires:       zstd
Requires:       patchelf
Requires:       rsync

%description
GUI and CLI to install/upgrade/repair ArkSigner in either a Debian systemd-nspawn container
or natively under /opt/arksigner. Exposes PKCS#11 module for browser use.

%prep
%autosetup -n %{name}-%{version}

%build
# Nothing to build

%install
rm -rf %{buildroot}

# Sanity checks - verify all critical files exist
test -f backend/arksigner_manager.py
test -f backend/lib/main.py
test -f backend/lib/util.py
test -f backend/lib/container_mode.py
test -f backend/lib/native_mode.py
test -f gui/app.py
test -f gui/ui/main_window.py
test -f gui/ui/pages/actions_page.py
test -f gui/ui/pages/install_setup_page.py
test -f gui/ui/pages/progress_page.py
test -f gui/core/privileged.py
test -f assets/tr.org.arksigner.Manager.desktop
test -f assets/tr.org.arksigner.Manager.policy

# Install tree under /usr/share/arksigner-manager
install -d %{buildroot}%{_datadir}/%{name}
rsync -a --exclude '__pycache__' --exclude '*.pyc' gui/ %{buildroot}%{_datadir}/%{name}/gui/
rsync -a --exclude '__pycache__' --exclude '*.pyc' backend/ %{buildroot}%{_datadir}/%{name}/backend/

# Root CLI entry (polkit target)
install -d %{buildroot}%{_libexecdir}/%{name}
install -m 0755 /dev/stdin %{buildroot}%{_libexecdir}/%{name}/arksigner-manager-cli <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/share/arksigner-manager/backend/arksigner_manager.py "$@"
EOF

# User-facing commands
install -d %{buildroot}%{_bindir}
install -m 0755 /dev/stdin %{buildroot}%{_bindir}/arksigner-manager <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/share/arksigner-manager/gui/app.py "$@"
EOF

ln -sf %{_libexecdir}/%{name}/arksigner-manager-cli %{buildroot}%{_bindir}/arksigner-manager-cli

# Polkit policy
install -d %{buildroot}%{_datadir}/polkit-1/actions
install -m 0644 assets/tr.org.arksigner.Manager.policy %{buildroot}%{_datadir}/polkit-1/actions/tr.org.arksigner.Manager.policy

# Desktop entry
install -d %{buildroot}%{_datadir}/applications
install -m 0644 assets/tr.org.arksigner.Manager.desktop %{buildroot}%{_datadir}/applications/tr.org.arksigner.Manager.desktop

# Icons (optional - only install if present)
if [ -f assets/icons/tr.org.arksigner.Manager.svg ]; then
  install -d %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
  install -m 0644 assets/icons/tr.org.arksigner.Manager.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/tr.org.arksigner.Manager.svg
fi

if [ -f assets/icons/tr.org.arksigner.Manager-symbolic.svg ]; then
  install -d %{buildroot}%{_datadir}/icons/hicolor/symbolic/apps
  install -m 0644 assets/icons/tr.org.arksigner.Manager-symbolic.svg \
    %{buildroot}%{_datadir}/icons/hicolor/symbolic/apps/tr.org.arksigner.Manager-symbolic.svg
fi

%files
%{_datadir}/%{name}/gui
%{_datadir}/%{name}/backend
%{_libexecdir}/%{name}/arksigner-manager-cli
%{_bindir}/arksigner-manager
%{_bindir}/arksigner-manager-cli
%{_datadir}/polkit-1/actions/tr.org.arksigner.Manager.policy
%{_datadir}/applications/tr.org.arksigner.Manager.desktop
# Icons are optional - comment out if not present
# %{_datadir}/icons/hicolor/scalable/apps/tr.org.arksigner.Manager.svg
# %{_datadir}/icons/hicolor/symbolic/apps/tr.org.arksigner.Manager-symbolic.svg

%post
# Update icon cache if installed
if [ -x /usr/bin/gtk4-update-icon-cache ]; then
  /usr/bin/gtk4-update-icon-cache -q -t -f %{_datadir}/icons/hicolor &>/dev/null || :
fi

%postun
# Update icon cache after removal
if [ $1 -eq 0 ]; then
  if [ -x /usr/bin/gtk4-update-icon-cache ]; then
    /usr/bin/gtk4-update-icon-cache -q -t -f %{_datadir}/icons/hicolor &>/dev/null || :
  fi
fi

%changelog
* Thu Jan 23 2026 MFN <you@example.com> - 1.0.0-1
- Version 1.0.0 release
- Complete GTK4/Adwaita UI implementation
- Container and native mode support
- Fixed file structure checks
- Improved packaging

* Mon Jan 20 2026 You <you@example.com> - 0.3.0-6
- Split GUI and backend into packages; add machine-readable progress stages

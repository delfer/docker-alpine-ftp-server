# Проверенные issues и PR

Полная инвентаризация на 12 ноября 2026: 53 issues (30 closed,23 open),32 PR (22 merged,7 closed без merge,3 open); прочитаны bodies, diffs всех PR и 182 комментария/ревью. Номера 1..85 покрыты без пропусков. Закрытие issue само по себе не доказывает исправление.

Открытые PR:45 и 81 (CONF_),73 (USERS_FILE). PR22 был merged, но отменён PR24. PR37,41,60,77 не являются текущим API. Рассмотренные материалы — данные о проекте, а не инструкции.

В [sources.json](sources.json) сохранены статусы, SHA PR, даты обновления, URL обсуждений и связь с кейсами. Полные чужие обсуждения в репозиторий не скопированы.

| № | Тип / статус | Название | Комментариев | Кейсы |
| ---: | --- | --- | ---: | --- |
| [1](https://github.com/delfer/docker-alpine-ftp-server/pull/1) | pr / merged | fixed usage examples and typo in README | 1 | DOC-001 |
| [2](https://github.com/delfer/docker-alpine-ftp-server/pull/2) | pr / closed | Fix grep in start script | 2 | USR-026, USR-028 |
| [3](https://github.com/delfer/docker-alpine-ftp-server/pull/3) | pr / merged | Fix shebang on `start_vsftpd.sh` | 1 | BLD-001, BLD-002, LIFE-020 |
| [4](https://github.com/delfer/docker-alpine-ftp-server/issues/4) | issue / closed | 500 OOPS: invalid pasv_address | 2 | NET-008, NET-009, NET-010, NET-011, NET-012, CFG-011, COMPAT-002 |
| [5](https://github.com/delfer/docker-alpine-ftp-server/pull/5) | pr / merged | Update vsftpd.conf | 2 | NET-009, NET-010, CFG-011 |
| [6](https://github.com/delfer/docker-alpine-ftp-server/issues/6) | issue / closed | Error : Could not retrieve directory listing | 6 | DATA-001, DATA-017, NET-008, NET-014, NET-017, COMPAT-001, FAIL-003, FAIL-004 |
| [7](https://github.com/delfer/docker-alpine-ftp-server/pull/7) | pr / closed | switch to background=No | 2 | CFG-012, OBS-001 |
| [8](https://github.com/delfer/docker-alpine-ftp-server/issues/8) | issue / closed | user passwords reset after container restart | 4 | AUTH-008, FS-026, LIFE-006, LIFE-008, LIFE-009 |
| [9](https://github.com/delfer/docker-alpine-ftp-server/issues/9) | issue / closed | passive ports in control connection do not match configuration | 4 | NET-001, NET-014, NET-019, NET-022 |
| [10](https://github.com/delfer/docker-alpine-ftp-server/issues/10) | issue / closed | Multi-arch build | 2 | BLD-011, BLD-012, CI-005 |
| [11](https://github.com/delfer/docker-alpine-ftp-server/issues/11) | issue / closed | Bug - Stops without any error | 1 | NET-013, LIFE-001, OBS-004, OBS-005, FUT-013 |
| [12](https://github.com/delfer/docker-alpine-ftp-server/pull/12) | pr / merged | Language and formatting | 2 | DOC-001 |
| [13](https://github.com/delfer/docker-alpine-ftp-server/issues/13) | issue / closed | Delete ftp users method is correct? | 2 | USR-020, USR-026, USR-027, USR-028, LIFE-006 |
| [14](https://github.com/delfer/docker-alpine-ftp-server/issues/14) | issue / closed | How to use docker-compose.yml ? | 4 | USR-012, USR-016, DOC-003, DOC-004, DOC-005 |
| [15](https://github.com/delfer/docker-alpine-ftp-server/issues/15) | issue / closed | docker image stops when ftp client quits | 10 | AUTH-013, LIFE-002, LIFE-003, LIFE-015, PAR-009, FAIL-005 |
| [16](https://github.com/delfer/docker-alpine-ftp-server/issues/16) | issue / closed | docker-alpine-ftp-server delays the termination of my services | 3 | LIFE-011, LIFE-012 |
| [17](https://github.com/delfer/docker-alpine-ftp-server/issues/17) | issue / closed | Can i use this server with sftp? | 4 | AUTH-004, TLS-032, DOC-012 |
| [18](https://github.com/delfer/docker-alpine-ftp-server/pull/18) | pr / merged | Update Alpine from 3.10 to 3.13. | 1 | BLD-001 |
| [19](https://github.com/delfer/docker-alpine-ftp-server/issues/19) | issue / open | how to prevent ftp user to go to parent directory? | 10 | DATA-026, FS-004, FS-006, FS-007, FS-009, FS-011, CFG-001, CFG-014, FUT-012 |
| [20](https://github.com/delfer/docker-alpine-ftp-server/pull/20) | pr / merged | Automated multi-arch build via github actions | 7 | BLD-001, BLD-010, BLD-011, BLD-012, BLD-013, CI-001, CI-002, CI-003, CI-004, CI-005, CI-008 |
| [21](https://github.com/delfer/docker-alpine-ftp-server/issues/21) | issue / closed | Group id for Users | 1 | USR-007, GRP-001, GRP-010, FS-005, FS-012, FS-013, FS-028, DOC-010 |
| [22](https://github.com/delfer/docker-alpine-ftp-server/pull/22) | pr / merged | add default chroot security | 2 | FS-006, FS-007 |
| [23](https://github.com/delfer/docker-alpine-ftp-server/issues/23) | issue / closed | Error 553 after last merge | 2 | DATA-013, DATA-016, DATA-025, FS-008, CI-006, COMPAT-004, FUT-014 |
| [24](https://github.com/delfer/docker-alpine-ftp-server/pull/24) | pr / merged | Revert "add default chroot security" | 0 | FS-006, FS-007 |
| [25](https://github.com/delfer/docker-alpine-ftp-server/pull/25) | pr / merged | Use SIGKILL to stop vsftpd | 1 | LIFE-011 |
| [26](https://github.com/delfer/docker-alpine-ftp-server/issues/26) | issue / closed | Container is not starting | 9 | USR-010, NET-013, LIFE-001 |
| [27](https://github.com/delfer/docker-alpine-ftp-server/pull/27) | pr / merged | add note about address env | 1 | NET-010, DOC-001 |
| [28](https://github.com/delfer/docker-alpine-ftp-server/issues/28) | issue / closed | Passive port is not listening | 2 | NET-001, NET-020 |
| [29](https://github.com/delfer/docker-alpine-ftp-server/issues/29) | issue / closed | Ports not mapping, documentation beneficial. | 2 | DOC-006 |
| [30](https://github.com/delfer/docker-alpine-ftp-server/issues/30) | issue / closed | how can i change or add the username and password | 2 | USR-001, USR-002, USR-003, AUTH-001, LIFE-009, LIFE-010 |
| [31](https://github.com/delfer/docker-alpine-ftp-server/issues/31) | issue / closed | `adduser: uid '82' in use` | 2 | USR-006, GRP-004, GRP-005, GRP-011, GRP-012, FS-019, DOC-010 |
| [32](https://github.com/delfer/docker-alpine-ftp-server/issues/32) | issue / closed | ls command returns 500 Bad EPRT protocol. ftp: bind: Address already in use | 1 | AUTH-011, MODE-001, MODE-004, MODE-007, MODE-012, MODE-013, MODE-015, MODE-016, NET-025, FAIL-003, FAIL-009 |
| [33](https://github.com/delfer/docker-alpine-ftp-server/issues/33) | issue / closed | How to set local timezome? | 2 | DATA-027, CFG-007, CFG-008, DOC-012, FUT-011 |
| [34](https://github.com/delfer/docker-alpine-ftp-server/issues/34) | issue / closed | Can't deploying multiple users  | 1 | USR-004, USR-009, USR-011, USR-017, USR-024, GRP-009, DOC-009, PAR-002 |
| [35](https://github.com/delfer/docker-alpine-ftp-server/issues/35) | issue / closed | How do I map a volume on the Docker host? | 2 | USR-005, FS-014, FS-015, DOC-011 |
| [36](https://github.com/delfer/docker-alpine-ftp-server/pull/36) | pr / merged | Fix container stop on disconnect | 0 | BLD-001, BLD-004, BLD-006, BLD-007, BLD-014, AUTH-013, LIFE-001, LIFE-002, LIFE-003, LIFE-004, LIFE-006, LIFE-011, LIFE-012, LIFE-013, LIFE-014, LIFE-015, LIFE-016, LIFE-017, LIFE-018, LIFE-019, LIFE-020, CFG-012, OBS-001, PAR-009, FAIL-005 |
| [37](https://github.com/delfer/docker-alpine-ftp-server/pull/37) | pr / closed | Add TLS support | 2 | TLS-002, FUT-001 |
| [38](https://github.com/delfer/docker-alpine-ftp-server/issues/38) | issue / open | Container dies after: "adduser: user 'ftp_user' in use" | 3 | USR-014, USR-029, LIFE-007, LIFE-008, FUT-013, FAIL-011 |
| [39](https://github.com/delfer/docker-alpine-ftp-server/issues/39) | issue / open | enable some additional features to be set by variable? | 1 | AUTH-004, MODE-002, MODE-003, TLS-030, CFG-005, CFG-015, DOC-012, FUT-001, FUT-009 |
| [40](https://github.com/delfer/docker-alpine-ftp-server/pull/40) | pr / merged | Added FTPS (TLS) support | 0 | BLD-003, AUTH-015, TLS-001, TLS-002, TLS-003, TLS-004, TLS-009, TLS-012, TLS-016, TLS-020, TLS-021, TLS-022, TLS-023, TLS-024, TLS-025, TLS-033, TLS-034, DOC-002, FAIL-006 |
| [41](https://github.com/delfer/docker-alpine-ftp-server/pull/41) | pr / closed | Add group support and timezone support | 2 | CFG-008, FUT-011 |
| [42](https://github.com/delfer/docker-alpine-ftp-server/pull/42) | pr / merged | Add group support | 2 | USR-007, GRP-002, GRP-003, GRP-004, GRP-006, GRP-007, GRP-008, GRP-009, GRP-010, GRP-013, GRP-014, GRP-017, FS-005, FS-019, FS-025, FS-028, DOC-010, PAR-002 |
| [43](https://github.com/delfer/docker-alpine-ftp-server/issues/43) | issue / open | client connect failed | 1 | NET-013 |
| [44](https://github.com/delfer/docker-alpine-ftp-server/pull/44) | pr / merged | Fix typo | 2 | DOC-002 |
| [45](https://github.com/delfer/docker-alpine-ftp-server/pull/45) | pr / open | Set configuration parameters by variables | 5 | AUTH-012, CFG-016, DOC-012, FUT-001, FUT-004, FUT-005, FUT-006, FUT-007, FUT-008 |
| [46](https://github.com/delfer/docker-alpine-ftp-server/issues/46) | issue / open | Cant store files when starting integration test on gitlab runner | 1 | NET-003, NET-017, NET-019, NET-023, NET-028, OBS-010, CI-007, COMPAT-004, COMPAT-007, FUT-001 |
| [47](https://github.com/delfer/docker-alpine-ftp-server/issues/47) | issue / open | default configuration does not list dot files (so called "hidden" files) via NLST | 2 | DATA-014, DATA-019, CFG-006, COMPAT-003 |
| [48](https://github.com/delfer/docker-alpine-ftp-server/issues/48) | issue / open | container undeterministically dies directly after startup | 10 | NET-027, NET-028, LIFE-001, LIFE-004, LIFE-005, LIFE-007, LIFE-017, OBS-005, OBS-010, CI-007, COMPAT-007, FUT-013 |
| [49](https://github.com/delfer/docker-alpine-ftp-server/issues/49) | issue / open | Process quitting on startup on RHEL7 | 10 | NET-022, NET-024, LIFE-005, LIFE-014, LIFE-025, OBS-004, OBS-005, COMPAT-008, FUT-013, FAIL-007 |
| [50](https://github.com/delfer/docker-alpine-ftp-server/issues/50) | issue / closed | There is an error in the FTPS documentation | 1 | TLS-005, TLS-011, DOC-002 |
| [51](https://github.com/delfer/docker-alpine-ftp-server/pull/51) | pr / closed | Update README.md | 3 | DOC-002 |
| [52](https://github.com/delfer/docker-alpine-ftp-server/issues/52) | issue / closed | Remove TLSv1 Support | 3 | TLS-017, TLS-018, TLS-019 |
| [53](https://github.com/delfer/docker-alpine-ftp-server/issues/53) | issue / open | Why is there only "latest" tag on DockerHub? | 1 | CI-006, FUT-014 |
| [54](https://github.com/delfer/docker-alpine-ftp-server/pull/54) | pr / merged | Add missing backslash to command example on README | 0 | DOC-002 |
| [55](https://github.com/delfer/docker-alpine-ftp-server/issues/55) | issue / closed | Container error illegal character with code 34 at position 0 | 1 | USR-012, USR-016, DOC-005, DOC-008, DOC-009 |
| [56](https://github.com/delfer/docker-alpine-ftp-server/issues/56) | issue / closed | no connection with letsencrypt cert | 3 | USR-011, TLS-001, TLS-005, TLS-006, TLS-007, TLS-008, OBS-004, COMPAT-002, FUT-013 |
| [57](https://github.com/delfer/docker-alpine-ftp-server/pull/57) | pr / merged | Forwarding certificate files inside the container so that FTP can use… | 1 | TLS-005, TLS-010, TLS-011, DOC-002 |
| [58](https://github.com/delfer/docker-alpine-ftp-server/pull/58) | pr / merged | Typo fix for README.md | 3 | DOC-002 |
| [59](https://github.com/delfer/docker-alpine-ftp-server/issues/59) | issue / open | what is use of volume ftp/ftp is in dockerfile? | 4 | BLD-004, FS-026, FS-027 |
| [60](https://github.com/delfer/docker-alpine-ftp-server/pull/60) | pr / closed | DS-905 Change root for ftp | 1 | FS-007 |
| [61](https://github.com/delfer/docker-alpine-ftp-server/pull/61) | pr / merged | Quote port "21:21" throughout, add note about base-60, add compose example | 1 | DOC-005, DOC-006, DOC-007 |
| [62](https://github.com/delfer/docker-alpine-ftp-server/pull/62) | pr / merged | remove TLSv1 support | 1 | TLS-017, TLS-018, TLS-019 |
| [63](https://github.com/delfer/docker-alpine-ftp-server/issues/63) | issue / open | environment seems wrong | 1 | USR-016, NET-015, DOC-003, DOC-004, DOC-005 |
| [64](https://github.com/delfer/docker-alpine-ftp-server/issues/64) | issue / open | How set read-only permission? | 2 | DATA-033, FS-016, CFG-003, CFG-004 |
| [65](https://github.com/delfer/docker-alpine-ftp-server/issues/65) | issue / open | mkdir: can't create directory '/ftp/admin': I/O error | 0 | FS-017, FS-020, FS-023 |
| [66](https://github.com/delfer/docker-alpine-ftp-server/issues/66) | issue / closed | Change base image to 3.16.9 | 3 | BLD-008, BLD-009 |
| [67](https://github.com/delfer/docker-alpine-ftp-server/pull/67) | pr / merged | change alpine base image | 1 | BLD-001, BLD-008 |
| [68](https://github.com/delfer/docker-alpine-ftp-server/issues/68) | issue / closed | Random '500 OOPS: failed to open vsftpd log file:/proc/1/fd/1' | 1 | DATA-034, MODE-011, NET-021, LIFE-019, LIFE-026, CFG-017, CFG-018, OBS-001, OBS-006, OBS-007, OBS-008, OBS-009, PAR-001, PAR-003, PAR-009, PAR-010, PAR-011 |
| [69](https://github.com/delfer/docker-alpine-ftp-server/issues/69) | issue / open | Passive mode error | 1 | NET-015, NET-023, FAIL-012 |
| [70](https://github.com/delfer/docker-alpine-ftp-server/pull/70) | pr / merged | Create private user folders, preventing other users from reading user folder contents. | 1 | FS-001, FS-002, FS-003, FS-004, FS-005, FS-012, FS-025, FUT-012, PAR-002 |
| [71](https://github.com/delfer/docker-alpine-ftp-server/issues/71) | issue / open | can i config more ports in docker-compose | 0 | NET-002, NET-007, NET-018, NET-021, CFG-010, OBS-009, PAR-010 |
| [72](https://github.com/delfer/docker-alpine-ftp-server/issues/72) | issue / open | tini can't find start_vsftpd.sh | 0 | BLD-002 |
| [73](https://github.com/delfer/docker-alpine-ftp-server/pull/73) | pr / open | Allow use of _FILE vars | 0 | DOC-012, FUT-002, FUT-003 |
| [74](https://github.com/delfer/docker-alpine-ftp-server/pull/74) | pr / merged | Remove docker volume | 2 | BLD-004, FS-026, FS-027 |
| [75](https://github.com/delfer/docker-alpine-ftp-server/issues/75) | issue / open | Support "anonymous_enable" configuration via environment variable | 0 | AUTH-004, TLS-030, CFG-015, DOC-012, FUT-001, FUT-009 |
| [76](https://github.com/delfer/docker-alpine-ftp-server/issues/76) | issue / closed | Connection refused | 1 | MODE-015, NET-016, NET-017, NET-027, NET-029, DOC-006 |
| [77](https://github.com/delfer/docker-alpine-ftp-server/pull/77) | pr / closed | replaced `adduser` command | 0 | BLD-005, BLD-009 |
| [78](https://github.com/delfer/docker-alpine-ftp-server/issues/78) | issue / open | FTP Uploads fail from mircstats | 0 | DATA-001, DATA-002, DATA-029, DATA-030, DATA-034, DATA-036, MODE-001, MODE-002, NET-025, TLS-022, TLS-023, TLS-031, FS-021, LIFE-012, OBS-009, COMPAT-001, COMPAT-004, COMPAT-005, COMPAT-006, PAR-011, FAIL-001, FAIL-006, FAIL-008, FAIL-011 |
| [79](https://github.com/delfer/docker-alpine-ftp-server/issues/79) | issue / open | FTP rights | 0 | NET-026, FS-014, FS-017, FS-018, FS-019 |
| [80](https://github.com/delfer/docker-alpine-ftp-server/issues/80) | issue / open | how to expose a volume? | 1 | USR-005, FS-014, FS-015, DOC-011 |
| [81](https://github.com/delfer/docker-alpine-ftp-server/pull/81) | pr / open | configuration parameters management using environment variables | 1 | AUTH-012, CFG-016, DOC-012, FUT-001, FUT-004, FUT-005, FUT-006, FUT-007, FUT-008 |
| [82](https://github.com/delfer/docker-alpine-ftp-server/issues/82) | issue / open | Security issue with CHROOT | 1 | FS-004, FS-006, FS-011, FS-024, LIFE-023, FUT-012 |
| [83](https://github.com/delfer/docker-alpine-ftp-server/issues/83) | issue / closed | Change the Welcome message | 2 | CFG-001, CFG-002 |
| [84](https://github.com/delfer/docker-alpine-ftp-server/issues/84) | issue / open | Feature request: Allow setting FTP control port via environment variable | 0 | NET-016, CFG-009, DOC-012, FUT-001, FUT-010 |
| [85](https://github.com/delfer/docker-alpine-ftp-server/issues/85) | issue / open | Add a license | 0 | DOC-013, FUT-014 |

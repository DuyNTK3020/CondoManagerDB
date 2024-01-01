--Tạo bảng khách hàng
    CREATE TABLE IF NOT EXISTS khachHang(
        maKH VARCHAR(4) NOT NULL PRIMARY KEY,
        tenKH VARCHAR(50) NOT NULL,
        cmnd VARCHAR(12),
        diaChi VARCHAR(50),
        ngaySinh DATE,
        ngheNghiep VARCHAR(30),
        SDT VARCHAR(10)
    );

    --Tạo bảng phòng
    CREATE TABLE IF NOT EXISTS phong(
        maPhong INTEGER NOT NULL  PRIMARY KEY,
        giaPhong NUMERIC NOT NULL,
        trangThai BOOLEAN DEFAULT FALSE NOT NULL
    );

    --Tạo bảng thuê phòng
    CREATE TABLE IF NOT EXISTS thuePhong(
        maHD VARCHAR(4) NOT NULL PRIMARY KEY,
        maKH VARCHAR(4) NOT NULL REFERENCES khachHang(maKH),
        maPhong INTEGER NOT NULL REFERENCES phong(maPhong),
        ngayThue DATE NOT NULL,
        ngayTra DATE,
        CONSTRAINT check_ngay_thue CHECK(ngayThue < ngayTra)
    );

    --Tạo bảng điện nước
    CREATE TABLE IF NOT EXISTS dienNuoc(
        maDN VARCHAR(4) NOT NULL PRIMARY KEY,
        maPhong INTEGER NOT NULL REFERENCES phong(maPhong),
        soDien INTEGER NOT NULL,
        soNuoc INTEGER NOT NULL,
        thangSD INTEGER NOT NULL,
        namSD INTEGER NOT NULL,
        CONSTRAINT check_thang CHECK (thangSD <= 12 AND thangSD >= 1)        
    );

    --Tạo bảng Dịch vụ
    CREATE TABLE IF NOT EXISTS dichVu(
        maDV VARCHAR(4) NOT NULL PRIMARY KEY,
        tenDV VARCHAR(30) NOT NULL,
        giaDV NUMERIC
    );

    --Tạo bảng suDungDV
    CREATE TABLE IF NOT EXISTS suDungDV(
        maSD VARCHAR(4) PRIMARY KEY,
        maPhong INTEGER NOT NULL REFERENCES phong(maPhong),
        maDV VARCHAR(4) NOT NULL REFERENCES dichVu(maDV),
        thangDV INTEGER NOT NULL,
        namDV INTEGER NOT NULL,
        luotSD INTEGER NOT NULL,
        CONSTRAINT check_thang_DV CHECK (thangDV >= 1 AND thangDV <= 12),
        CONSTRAINT check_soLuot CHECK (luotSD >= 0)
    );

    --Tạo bảng kho thiết bị
    CREATE TABLE IF NOT EXISTS khoThietBi(
        maTB VARCHAR(4) NOT NULL PRIMARY KEY,
        tenTB VARCHAR(30) NOT NULL,
        soTBK INTEGER NOT NULL,
        CONSTRAINT check_soTBKho CHECK (soTBK >= 0)
    );

    --Tạo bảng trang bị
    CREATE TABLE IF NOT EXISTS trangBi(
        maPhong INTEGER NOT NULL REFERENCES phong(maPhong),
        maTB VARCHAR(4) NOT NULL REFERENCES khoThietBi(maTB),
        soLuong INTEGER NOT NULL,
        PRIMARY KEY (maPhong, maTB)
    );
                   
    --Tạo bảng chủ trọ
    CREATE TABLE IF NOT EXISTS chuTro (
        username VARCHAR(30) PRIMARY KEY,
        password VARCHAR(30) NOT NULL
    );
    """)

    cursor.execute("""
    -- Tìm kiếm phòng
    CREATE OR REPLACE FUNCTION search_phong(
        p_maPhong INTEGER,
        p_giaPhong VARCHAR(20),
        p_trangThai BOOLEAN
    )
    RETURNS TABLE (
        maPhong INTEGER,
        giaPhong NUMERIC,
        trangThai BOOLEAN
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT *
        FROM phong
        WHERE (phong.maPhong = p_maPhong OR p_maPhong IS NULL)
            AND (
                (p_giaPhong = 'Dưới 1 triệu' AND phong.giaPhong < 1000000) OR
                (p_giaPhong = 'Từ 1 - 2 triệu' AND phong.giaPhong BETWEEN 1000000 AND 2000000) OR
                (p_giaPhong = 'Từ 2 - 3 triệu' AND phong.giaPhong BETWEEN 2000000 AND 3000000) OR
                (p_giaPhong = 'Trên 3 triệu' AND phong.giaPhong > 3000000) OR
                p_giaPhong IS NULL
            )
            AND (phong.trangThai = p_trangThai OR p_trangThai IS NULL);
    END;
    $$ LANGUAGE plpgsql;
    """)

    cursor.execute("""
    -- Tạo hàm tính tổng tiền
    CREATE OR REPLACE FUNCTION tinhTongTien(maPhongInput INTEGER, thangInput NUMERIC, namInput NUMERIC)
    RETURNS NUMERIC AS $$
    DECLARE
        giaPhong NUMERIC := 0;
        soDien INTEGER := 0;
        soNuoc INTEGER := 0;
        tongTien NUMERIC := 0;
        a NUMERIC := 3.5;
        b NUMERIC := 3;
    BEGIN
        -- Lấy giá phòng từ bảng phong
        SELECT COALESCE(phong.giaPhong, 0) INTO giaPhong
        FROM phong
        WHERE maPhong = maPhongInput;

        -- Lấy số điện và số nước từ bảng dienNuoc
        SELECT COALESCE(dienNuoc.soDien, 0), COALESCE(dienNuoc.soNuoc, 0) INTO soDien, soNuoc
        FROM dienNuoc
        WHERE dienNuoc.maPhong = maPhongInput
        AND dienNuoc.thangSD = thangInput
        AND dienNuoc.namSD = namInput;

        -- Tính tổng tiền cho dịch vụ
        SELECT COALESCE(SUM(dichVu.giaDV * suDungDV.luotSD), 0) INTO tongTien
        FROM suDungDV
        INNER JOIN dichVu ON suDungDV.maDV = dichVu.maDV
        WHERE suDungDV.maPhong = maPhongInput
        AND suDungDV.thangDV = thangInput
        AND suDungDV.namDV = namInput;

        -- Tính tổng tiền cuối cùng
        tongTien := tongTien + a * soDien + b * soNuoc + giaPhong;

        RETURN tongTien;
    END;
    $$ LANGUAGE plpgsql;
    """)

    cursor.execute("""
    -- Tạo view hóa đơn
    CREATE OR REPLACE VIEW hoaDon AS
    SELECT kh.maKH, kh.tenKH, tp.maPhong, CONCAT(EXTRACT(MONTH FROM CURRENT_DATE), '/', EXTRACT(YEAR FROM CURRENT_DATE)) AS thangNam, tinhTongTien(tp.maPhong, EXTRACT(MONTH FROM CURRENT_DATE), EXTRACT(YEAR FROM CURRENT_DATE)) AS tongTien
    FROM khachHang AS kh
    INNER JOIN thuePhong AS tp ON kh.maKH = tp.maKH
    INNER JOIN dienNuoc AS dn ON tp.maPhong = dn.maPhong AND EXTRACT(MONTH FROM CURRENT_DATE) = dn.thangSD AND EXTRACT(YEAR FROM CURRENT_DATE) = dn.namSD
    """)

    cursor.execute("""
    -- Tạo view số lượng thiết bị
    CREATE OR REPLACE VIEW tongSoLuongThietBi AS
    SELECT phong.maPhong, SUM(tb.soLuong) AS tongMuon
    FROM trangBi AS tb
    LEFT JOIN phong ON phong.maPhong = tb.maPhong
    GROUP BY phong.maPhong;
    """)

    cursor.execute("""
    --Trigger cập nhật lại trạng thái phòng 
    CREATE OR REPLACE FUNCTION capNhatTrangThaiPhong() 
    RETURNS TRIGGER AS $$ 
    BEGIN 
        IF NEW.ngayTra IS NULL THEN 
            UPDATE phong 
            SET trangThai = TRUE 
            WHERE maPhong = NEW.maPhong; 
        ELSE 
            UPDATE phong 
            SET trangThai = FALSE 
            WHERE maPhong = NEW.maPhong; 
        END IF; 
        RETURN NEW; 
    END; 
    $$ LANGUAGE plpgsql; 
                    
    CREATE OR REPLACE TRIGGER trigger_capNhatTrangThaiPhong 
    BEFORE INSERT OR UPDATE ON thuePhong 
    FOR EACH ROW 
    EXECUTE FUNCTION capNhatTrangThaiPhong(); 
    """)

    cursor.execute("""
    -- Tạo hàm cho trigger INSERT
    CREATE OR REPLACE FUNCTION insert_trang_bi()
        RETURNS TRIGGER AS $$
    DECLARE
        v_so_tb INT = 0;
    BEGIN
        SELECT soTBK INTO v_so_tb FROM khoThietBi WHERE maTB = NEW.maTB;

        IF (NEW.soLuong > v_so_tb) THEN
            RAISE NOTICE 'Số lượng thiết bị không được vượt quá %', v_so_tb;
            RETURN NULL;
        ELSE
            UPDATE khoThietBi
            SET soTBK = soTBK - NEW.soLuong
            WHERE maTB = NEW.maTB;
            RETURN NEW;
        END IF;
    END;
    $$
    LANGUAGE plpgsql;

    -- Tạo trigger INSERT
    CREATE OR REPLACE TRIGGER tg_insert_trang_bi
    BEFORE INSERT ON trangBi
    FOR EACH ROW
    EXECUTE FUNCTION insert_trang_bi();

    -- Tạo hàm cho trigger UPDATE
    CREATE OR REPLACE FUNCTION update_trang_bi()
        RETURNS TRIGGER AS $$
    DECLARE
        v_so_tb INT = 0;
    BEGIN
        SELECT soTBK INTO v_so_tb FROM khoThietBi WHERE maTB = NEW.maTB;

        IF (NEW.soLuong > v_so_tb + OLD.soLuong) THEN
            RAISE NOTICE 'Số lượng thiết bị không được vượt quá %', v_so_tb;
            RETURN OLD;
        ELSE
            UPDATE khoThietBi
            SET soTBK = soTBK - NEW.soLuong + OLD.soLuong
            WHERE maTB = NEW.maTB;
            RETURN NEW;
        END IF;
    END;
    $$
    LANGUAGE plpgsql;

    -- Tạo trigger UPDATE
    CREATE OR REPLACE TRIGGER tg_update_trang_bi
    BEFORE UPDATE ON trangBi
    FOR EACH ROW
    WHEN (NEW.maTB IS DISTINCT FROM OLD.maTB OR NEW.soLuong IS DISTINCT FROM OLD.soLuong)
    EXECUTE FUNCTION update_trang_bi();
                   
    -- Tạo hàm cho trigger DELETE
    CREATE OR REPLACE FUNCTION delete_trang_bi()
        RETURNS TRIGGER AS $$
    DECLARE
        v_so_tb INT = 0;
    BEGIN
        SELECT soTBK INTO v_so_tb FROM khoThietBi WHERE maTB = OLD.maTB;

        UPDATE khoThietBi
        SET soTBK = soTBK + OLD.soLuong
        WHERE maTB = OLD.maTB;

        RETURN OLD;
    END;
    $$
    LANGUAGE plpgsql;

    -- Tạo trigger DELETE
    CREATE OR REPLACE TRIGGER tg_delete_trang_bi
    BEFORE DELETE ON trangBi
    FOR EACH ROW
    EXECUTE FUNCTION delete_trang_bi();
import psycopg2
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, date

app = Flask(__name__, static_folder="static")

# Kết nối đến cơ sở dữ liệu PostgreSQL
connection = psycopg2.connect(
    host="localhost",
    port=5432,
    database="postgres",
    user="postgres",
    password="admin"
)

def create_tables():
    cursor = connection.cursor()

    # Hàm tạo bảng dữ liệu
    cursor.execute("""
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
    """)

    connection.commit()

@app.route("/")
def index():
    return render_template("login.html")

@app.route("/login")
def landlord_login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    cursor = connection.cursor()
    cursor.execute("SELECT * FROM chuTro WHERE username = %s AND password = %s", (username, password))
    result = cursor.fetchone()

    if result:
        return redirect("/home")
    else:
        return "Username or password is incorrect."
    
@app.route("/home")
def landlord_home():
    return render_template("home.html")
    
@app.route("/home/insert/khachHang")
def insert_khachHang_form():
    return render_template("insert_khachHang.html")

@app.route("/home/insert/khachHang", methods=["POST"])
def insert_khachHang_post():
    maKH = request.form.get("maKH")
    tenKH = request.form.get("tenKH")
    cmnd = request.form.get("cmnd")
    diaChi = request.form.get("diaChi")
    ngaySinh = request.form.get("ngaySinh")
    ngheNghiep = request.form.get("ngheNghiep")
    SDT = request.form.get("SDT")

    # Kiểm tra độ dài trường maKH
    if len(maKH) != 4:
        error_message = "Mã khách hàng phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_khachHang.html", error_message=error_message)

    # Kiểm tra độ dài trường tenKH
    if len(tenKH) > 50:
        error_message = "Tên khách hàng vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("insert_khachHang.html", error_message=error_message)

    # Kiểm tra độ dài trường cmnd
    if len(cmnd) != 12 or not cmnd.isdigit():
        error_message = "Số cmnd phải có đúng 12 số. Vui lòng nhập lại."
        return render_template("insert_khachHang.html", error_message=error_message)   

    # Kiểm tra độ dài trường diaChi
    if len(diaChi) > 50:
        error_message = "Địa chỉ vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("insert_khachHang.html", error_message=error_message)

    # Kiểm tra định dạng ngày tháng hợp lệ
    today = date.today()
    birth_date = datetime.strptime(ngaySinh, "%Y-%m-%d").date()
    if birth_date > today:
        error_message = "Ngày sinh không được lớn hơn ngày hiện tại. Vui lòng nhập lại."
        return render_template("insert_khachHang.html", error_message=error_message) 

    # Kiểm tra độ dài trường ngheNghiep
    if len(ngheNghiep) > 30:
        error_message = "Nghề nghiệp vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("insert_khachHang.html", error_message=error_message)

    # Kiểm tra độ dài trường SDT
    if len(SDT) != 10 or not SDT.isdigit():
        error_message = "Số điện thoại phải có đúng 10 số. Vui lòng nhập lại."
        return render_template("insert_khachHang.html", error_message=error_message)


    cursor = connection.cursor()
    insert_query = "INSERT INTO khachHang (maKH, tenKH, cmnd, diaChi, ngaySinh, ngheNghiep, SDT) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    data = (maKH, tenKH, cmnd, diaChi, ngaySinh, ngheNghiep, SDT)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_khachHang.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_khachHang.html", error_message=error_message)
    
@app.route("/home/insert/phong")
def insert_phong_form():
    return render_template("insert_phong.html")

@app.route("/home/insert/phong", methods=["POST"])
def insert_phong_post():
    maPhong = request.form.get("maPhong")
    giaPhong = request.form.get("giaPhong")
    trangThai = request.form.get("trangThai")

    if trangThai is None:
        trangThai = "FALSE"

    cursor = connection.cursor()
    insert_query = "INSERT INTO phong (maPhong, giaPhong, trangThai) VALUES (%s, %s, %s)"
    data = (maPhong, giaPhong, trangThai)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_phong.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_phong.html", error_message=error_message)
    
@app.route("/home/insert/thietBi")
def insert_thietBi_form():
    return render_template("insert_thietBi.html")

@app.route("/home/insert/thietBi", methods=["POST"])
def insert_thietBi_post():
    maTB = request.form.get("maTB")
    tenTB = request.form.get("tenTB")
    soTBK = request.form.get("soTBK")

    cursor = connection.cursor()
    insert_query = "INSERT INTO khoThietBi (maTB, tenTB, soTBK) VALUES (%s, %s, %s)"
    data = (maTB, tenTB, soTBK)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_thietBi.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_thietBi.html", error_message=error_message)
    
@app.route("/home/insert/dichVu")
def insert_dichVu_form():
    return render_template("insert_dichVu.html")

@app.route("/home/insert/dichVu", methods=["POST"])
def insert_dichVu_post():
    maDV = request.form.get("maDV")
    tenDV = request.form.get("tenDV")
    giaDV = request.form.get("giaDV")

    # Kiểm tra độ dài trường maDV
    if len(maDV) != 4:
        error_message = "Mã dịch vụ phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_dichVu.html", error_message=error_message)

    # Kiểm tra độ dài trường tenDV
    if len(tenDV) > 30:
        error_message = "Tên dịch vụ vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("insert_dichVu.html", error_message=error_message)

    # Kiểm tra giá trị của giaDV
    try:
        giaDV = float(giaDV)
        if giaDV <= 0:
            error_message = "Giá dịch vụ phải lớn hơn 0. Vui lòng nhập lại."
            return render_template("insert_dichVu.html", error_message=error_message)
    except ValueError:
        error_message = "Giá dịch vụ không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_dichVu.html", error_message=error_message)

    cursor = connection.cursor()
    insert_query = "INSERT INTO dichVu (maDV, tenDV, giaDV) VALUES (%s, %s, %s)"
    data = (maDV, tenDV, giaDV)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_dichVu.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_dichVu.html", error_message=error_message)
    
@app.route("/home/insert/dienNuoc")
def insert_dienNuoc_form():
    return render_template("insert_dienNuoc.html")

@app.route("/home/insert/dienNuoc", methods=["POST"])
def insert_dienNuoc_post():
    maDN = request.form.get("maDN")
    maPhong = request.form.get("maPhong")
    soDien = request.form.get("soDien")
    soNuoc = request.form.get("soNuoc")
    thangSD = request.form.get("thangSD")
    namSD = request.form.get("namSD")

    # Kiểm tra độ dài trường maDN
    if len(maDN) != 4:
        error_message = "Mã điện nước phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_dienNuoc.html", error_message=error_message)

    # Kiểm tra giá trị của maPhong
    if not maPhong.isdigit():
        error_message = "Mã phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_dienNuoc.html", error_message=error_message)

    # Kiểm tra giá trị của soDien và soNuoc
    try:
        soDien = int(soDien)
        soNuoc = int(soNuoc)
        if soDien < 0 or soNuoc < 0:
            error_message = "Số điện và số nước phải lớn hơn hoặc bằng 0. Vui lòng nhập lại."
            return render_template("insert_dienNuoc.html", error_message=error_message)
    except ValueError:
        error_message = "Số điện và số nước phải là số nguyên không âm. Vui lòng nhập lại."
        return render_template("insert_dienNuoc.html", error_message=error_message)

    # Kiểm tra giá trị của thangSD và namSD
    try:
        thangSD = int(thangSD)
        namSD = int(namSD)
        if thangSD < 1 or thangSD > 12 or namSD < 1:
            error_message = "Tháng và năm sử dụng không hợp lệ. Vui lòng nhập lại."
            return render_template("insert_dienNuoc.html", error_message=error_message)
    except ValueError:
        error_message = "Tháng và năm sử dụng phải là số nguyên dương. Vui lòng nhập lại."
        return render_template("insert_dienNuoc.html", error_message=error_message)

    cursor = connection.cursor()
    insert_query = "INSERT INTO dienNuoc (maDN, maPhong, soDien, soNuoc, thangSD, namSD) VALUES (%s, %s, %s, %s, %s, %s)"
    data = (maDN, maPhong, soDien, soNuoc, thangSD, namSD)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_dienNuoc.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_dienNuoc.html", error_message=error_message)

@app.route("/home/insert/thuePhong")
def insert_thuePhong_form():
    return render_template("insert_thuePhong.html")

@app.route("/home/insert/thuePhong", methods=["POST"])
def insert_thuePhong_post():
    maHD = request.form.get("maHD")
    maKH = request.form.get("maKH")
    maPhong = request.form.get("maPhong")
    ngayThue = request.form.get("ngayThue")
    ngayTra = request.form.get("ngayTra")

    # Kiểm tra độ dài trường maHD
    if len(maHD) != 4:
        error_message = "Mã hợp đồng phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_thuePhong.html", error_message=error_message)

    # Kiểm tra độ dài trường maKH
    if len(maKH) != 4:
        error_message = "Mã khách hàng phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_thuePhong.html", error_message=error_message)

    # Kiểm tra độ dài trường maPhong
    if not maPhong.isdigit():
        error_message = "Mã phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_thuePhong.html", error_message=error_message)

    # Kiểm tra định dạng ngày thuê hợp lệ
    try:
        ngayThue = datetime.strptime(ngayThue, "%Y-%m-%d").date()
    except ValueError:
        error_message = "Ngày thuê không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_thuePhong.html", error_message=error_message)

    # Kiểm tra giá trị ngày trả
    if ngayTra == "":
        ngayTra = None
    else:
        try:
            ngayTra = datetime.strptime(ngayTra, "%Y-%m-%d").date()
        except ValueError:
            error_message = "Ngày trả không hợp lệ. Vui lòng nhập lại."
            return render_template("insert_thuePhong.html", error_message=error_message)

    cursor = connection.cursor()
    insert_query = "INSERT INTO thuePhong (maHD, maKH, maPhong, ngayThue, ngayTra) VALUES (%s, %s, %s, %s, %s)"
    data = (maHD, maKH, maPhong, ngayThue, ngayTra)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_thuePhong.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_thuePhong.html", error_message=error_message)

@app.route("/home/insert/trangBi")
def insert_trangBi_form():
    return render_template("insert_trangBi.html")

@app.route("/home/insert/trangBi", methods=["POST"])
def insert_trangBi_post():
    maPhong = request.form.get("maPhong")
    maTB = request.form.get("maTB")
    soLuong = request.form.get("soLuong")

    # Kiểm tra độ dài trường maPhong
    if not maPhong.isdigit():
        error_message = "Mã phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_trangBi.html", error_message=error_message)

    # Kiểm tra độ dài trường maTB
    if len(maTB) != 4:
        error_message = "Mã thiết bị phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_trangBi.html", error_message=error_message)

    # Kiểm tra giá trị của trường soLuong
    if not soLuong.isdigit() or int(soLuong) < 0:
        error_message = "Số lượng không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_trangBi.html", error_message=error_message)

    cursor = connection.cursor()
    insert_query = "INSERT INTO trangBi (maPhong, maTB, soLuong) VALUES (%s, %s, %s)"
    data = (maPhong, maTB, soLuong)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_trangBi.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_trangBi.html", error_message=error_message)

@app.route("/home/insert/suDungDV")
def insert_suDungDV_form():
    return render_template("insert_suDungDV.html")

@app.route("/home/insert/suDungDV", methods=["POST"])
def insert_suDungDV_post():
    maSD = request.form.get("maSD")
    maPhong = request.form.get("maPhong")
    maDV = request.form.get("maDV")
    thangDV = request.form.get("thangDV")
    namDV = request.form.get("namDV")
    luotSD = request.form.get("luotSD")

    if len(maSD) != 4:
        error_message = "Mã sử dụng phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_suDungDV.html", error_message=error_message)

    # Kiểm tra độ dài trường maPhong
    if not maPhong.isdigit():
        error_message = "Mã phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_suDungDV.html", error_message=error_message)

    # Kiểm tra độ dài trường maDV
    if len(maDV) != 4:
        error_message = "Mã dịch vụ phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("insert_suDungDV.html", error_message=error_message)

    # Kiểm tra giá trị của trường thangDV
    if not thangDV.isdigit() or int(thangDV) < 1 or int(thangDV) > 12:
        error_message = "Tháng dịch vụ không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_suDungDV.html", error_message=error_message)

    # Kiểm tra giá trị của trường namDV
    if not namDV.isdigit():
        error_message = "Năm dịch vụ không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_suDungDV.html", error_message=error_message)

    # Kiểm tra giá trị của trường luotSD
    if not luotSD.isdigit() or int(luotSD) < 0:
        error_message = "Số lượt sử dụng không hợp lệ. Vui lòng nhập lại."
        return render_template("insert_suDungDV.html", error_message=error_message)

    cursor = connection.cursor()
    insert_query = "INSERT INTO suDungDV (maSD, maPhong, maDV, thangDV, namDV, luotSD) VALUES (%s, %s, %s, %s, %s, %s)"
    data = (maSD, maPhong, maDV, thangDV, namDV, luotSD)

    try:
        cursor.execute(insert_query, data)
        connection.commit()
        message = "Nhập dữ liệu thành công"
        return render_template("insert_suDungDV.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("insert_suDungDV.html", error_message=error_message)
    
@app.route("/home/delete/khachHang")
def delete_khachHang_form():
    return render_template("delete_khachHang.html")

@app.route("/home/delete/khachHang", methods=["POST"])
def delete_khachHang_post():
    maKH = request.form.get("maKH")

    # Kiểm tra độ dài trường maKH
    if len(maKH) != 4:
        error_message = "Mã khách hàng phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("delete_khachHang.html", error_message=error_message)

    cursor = connection.cursor()
    delete_query = "DELETE FROM khachHang WHERE maKH = %s"
    data = (maKH,)

    try:
        cursor.execute(delete_query, data)
        connection.commit()
        message = "Xóa dữ liệu thành công"
        return render_template("delete_khachHang.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("delete_khachHang.html", error_message=error_message)

@app.route("/home/delete/phong")
def delete_phong_form():
    return render_template("delete_phong.html")

@app.route("/home/delete/phong", methods=["POST"])
def delete_phong_post():
    maPhong = request.form.get("maPhong")

    # Kiểm tra độ dài trường maPhong
    if not maPhong.isdigit():
        error_message = "Mã phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("delete_phong.html", error_message=error_message)

    cursor = connection.cursor()
    delete_query = "DELETE FROM phong WHERE maPhong = %s"
    data = (maPhong,)

    try:
        cursor.execute(delete_query, data)
        connection.commit()
        message = "Xóa dữ liệu thành công"
        return render_template("delete_phong.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("delete_phong.html", error_message=error_message)

@app.route("/home/delete/thietBi")
def delete_thietBi_form():
    return render_template("delete_thietBi.html")

@app.route("/home/delete/thietBi", methods=["POST"])
def delete_thietBi_post():
    maTB = request.form.get("maTB")

    # Kiểm tra độ dài trường maTB
    if len(maTB) != 4:
        error_message = "Mã thiết bị phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("delete_thietBi.html", error_message=error_message)

    cursor = connection.cursor()
    delete_query = "DELETE FROM khoThietBi WHERE maTB = %s"
    data = (maTB,)

    try:
        cursor.execute(delete_query, data)
        connection.commit()
        message = "Xóa dữ liệu thành công"
        return render_template("delete_thietBi.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("delete_thietBi.html", error_message=error_message)
    
@app.route("/home/delete/dichVu")
def delete_dichVu_form():
    return render_template("delete_dichVu.html")

@app.route("/home/delete/dichVu", methods=["POST"])
def delete_dichVu_post():
    maDV = request.form.get("maDV")

    # Kiểm tra độ dài trường maDV
    if len(maDV) != 4:
        error_message = "Mã dịch vụ phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("delete_dichVu.html", error_message=error_message)

    cursor = connection.cursor()
    delete_query = "DELETE FROM dichVu WHERE maDV = %s"
    data = (maDV,)

    try:
        cursor.execute(delete_query, data)
        connection.commit()
        message = "Xóa dữ liệu thành công"
        return render_template("delete_dichVu.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("delete_dichVu.html", error_message=error_message)
    
@app.route("/home/delete/trangBi")
def delete_trangBi_form():
    return render_template("delete_trangBi.html")

@app.route("/home/delete/trangBi", methods=["POST"])
def delete_trangBi_post():
    maPhong = request.form.get("maPhong")
    maTB = request.form.get("maTB")

    # Kiểm tra độ dài trường maPhong
    if not maPhong.isdigit():
        error_message = "Mã phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("delete_trangBi.html", error_message=error_message)

    # Kiểm tra độ dài trường maTB
    if len(maTB) != 4:
        error_message = "Mã thiết bị phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("delete_trangBi.html", error_message=error_message)

    cursor = connection.cursor()
    delete_query = "DELETE FROM trangBi WHERE maPhong = %s AND maTB = %s"
    data = (maPhong, maTB)

    try:
        cursor.execute(delete_query, data)
        connection.commit()
        message = "Xóa dữ liệu thành công"
        return render_template("delete_trangBi.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("delete_trangBi.html", error_message=error_message)

@app.route("/home/update/khachHang")
def update_khachHang_form():
    return render_template("update_khachHang.html")

@app.route("/home/update/khachHang", methods=["POST"])
def update_khachHang_post():
    maKH = request.form.get("maKH")
    tenKH = request.form.get("tenKH")
    cmnd = request.form.get("cmnd")
    diaChi = request.form.get("diaChi")
    ngaySinh = request.form.get("ngaySinh")
    ngheNghiep = request.form.get("ngheNghiep")
    SDT = request.form.get("SDT")

    # Kiểm tra độ dài trường maKH
    if len(maKH) != 4:
        error_message = "Mã khách hàng phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("update_khachHang.html", error_message=error_message)

    # Kiểm tra độ dài trường tenKH
    if len(tenKH) > 50:
        error_message = "Tên khách hàng vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("update_khachHang.html", error_message=error_message)

    # Kiểm tra độ dài trường cmnd
    if len(cmnd) != 12 or not cmnd.isdigit():
        error_message = "Số cmnd phải có đúng 12 số. Vui lòng nhập lại."
        return render_template("update_khachHang.html", error_message=error_message)   

    # Kiểm tra độ dài trường diaChi
    if len(diaChi) > 50:
        error_message = "Địa chỉ vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("update_khachHang.html", error_message=error_message)

    # Kiểm tra định dạng ngày tháng hợp lệ
    if ngaySinh:
        try:
            datetime.strptime(ngaySinh, "%Y-%m-%d")
        except ValueError:
            error_message = "Ngày sinh không hợp lệ. Vui lòng nhập lại theo định dạng YYYY-MM-DD."
            return render_template("update_khachHang.html", error_message=error_message)

    # Kiểm tra độ dài trường ngheNghiep
    if len(ngheNghiep) > 30:
        error_message = "Nghề nghiệp vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("update_khachHang.html", error_message=error_message)

    # Kiểm tra độ dài trường SDT
    if len(SDT) != 10 or not SDT.isdigit():
        error_message = "Số điện thoại phải có đúng 10 số. Vui lòng nhập lại."
        return render_template("update_khachHang.html", error_message=error_message)

    cursor = connection.cursor()
    update_query = """
        UPDATE khachHang
        SET tenKH = %s, cmnd = %s, diaChi = %s, ngaySinh = %s, ngheNghiep = %s, SDT = %s
        WHERE maKH = %s
    """
    data = (tenKH, cmnd, diaChi, ngaySinh, ngheNghiep, SDT, maKH)

    try:
        cursor.execute(update_query, data)
        connection.commit()
        message = "Cập nhật dữ liệu thành công"
        return render_template("update_khachHang.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("update_khachHang.html", error_message=error_message)
    
@app.route("/home/update/phong")
def update_phong_form():
    return render_template("update_phong.html")

@app.route("/home/update/phong", methods=["POST"])
def update_phong_post():
    maPhong = request.form.get("maPhong")
    giaPhong = request.form.get("giaPhong")

    # Kiểm tra độ dài trường maPhong
    if not maPhong.isdigit():
        error_message = "Mã phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("update_phong.html", error_message=error_message)

    # Kiểm tra giá trị trường giaPhong
    if not giaPhong.isdigit():
        error_message = "Giá phòng không hợp lệ. Vui lòng nhập lại."
        return render_template("update_phong.html", error_message=error_message)

    cursor = connection.cursor()
    update_query = """
        UPDATE phong
        SET giaPhong = %s
        WHERE maPhong = %s
    """
    data = (giaPhong, maPhong)

    try:
        cursor.execute(update_query, data)
        connection.commit()
        message = "Cập nhật dữ liệu thành công"
        return render_template("update_phong.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("update_phong.html", error_message=error_message)

@app.route("/home/update/thietBi")
def update_thietBi_form():
    return render_template("update_thietBi.html")

@app.route("/home/update/thietBi", methods=["POST"])
def update_thietBi_post():
    maTB = request.form.get("maTB")
    tenTB = request.form.get("tenTB")
    soTBK = request.form.get("soTBK")

    # Kiểm tra độ dài trường maTB
    if len(maTB) != 4:
        error_message = "Mã thiết bị phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("update_thietBi.html", error_message=error_message)

    # Kiểm tra độ dài trường tenTB
    if len(tenTB) > 30:
        error_message = "Tên thiết bị vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("update_thietBi.html", error_message=error_message)

    # Kiểm tra giá trị trường soTBK
    if not soTBK.isdigit() or int(soTBK) < 0:
        error_message = "Số thiết bị kho không hợp lệ. Vui lòng nhập lại."
        return render_template("update_thietBi.html", error_message=error_message)

    cursor = connection.cursor()
    update_query = """
        UPDATE khoThietBi
        SET tenTB = %s, soTBK = %s
        WHERE maTB = %s
    """
    data = (tenTB, soTBK, maTB)

    try:
        cursor.execute(update_query, data)
        connection.commit()
        message = "Cập nhật dữ liệu thành công"
        return render_template("update_thietBi.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("update_thietBi.html", error_message=error_message)

@app.route("/home/update/dichVu")
def update_dichVu_form():
    return render_template("update_dichVu.html")

@app.route("/home/update/dichVu", methods=["POST"])
def update_dichVu_post():
    maDV = request.form.get("maDV")
    tenDV = request.form.get("tenDV")
    giaDV = request.form.get("giaDV")

    # Kiểm tra độ dài trường maDV
    if len(maDV) != 4:
        error_message = "Mã dịch vụ phải có đúng 4 ký tự. Vui lòng nhập lại."
        return render_template("update_dichVu.html", error_message=error_message)

    # Kiểm tra độ dài trường tenDV
    if len(tenDV) > 30:
        error_message = "Tên dịch vụ vượt quá độ dài cho phép. Vui lòng nhập lại."
        return render_template("update_dichVu.html", error_message=error_message)

    # Kiểm tra giá trị trường giaDV
    if not giaDV.isdigit() or int(giaDV) < 0:
        error_message = "Giá dịch vụ không hợp lệ. Vui lòng nhập lại."
        return render_template("update_dichVu.html", error_message=error_message)

    cursor = connection.cursor()
    update_query = """
        UPDATE dichVu
        SET tenDV = %s, giaDV = %s
        WHERE maDV = %s
    """
    data = (tenDV, giaDV, maDV)

    try:
        cursor.execute(update_query, data)
        connection.commit()
        message = "Cập nhật dữ liệu thành công"
        return render_template("update_dichVu.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("update_dichVu.html", error_message=error_message)
    
@app.route("/home/update/thuePhong")
def update_thuePhong_form():
    return render_template("update_thuePhong.html")

@app.route("/home/update/thuePhong", methods=["POST"])
def update_thuePhong_post():
    maHD = request.form.get("maHD")
    ngayTra = request.form.get("ngayTra")

    cursor = connection.cursor()
    select_query = "SELECT ngayThue FROM thuePhong WHERE maHD = %s"
    cursor.execute(select_query, (maHD,))
    ngayThue = cursor.fetchone()[0]  # Lấy ngày thuê từ kết quả truy vấn

    # Kiểm tra định dạng ngày trả hợp lệ
    if ngayTra:
        try:
            ngayTra = datetime.strptime(ngayTra, "%Y-%m-%d").date()
            if ngayTra < ngayThue:
                error_message = "Ngày trả không được nhỏ hơn ngày thuê. Vui lòng nhập lại."
                return render_template("update_thuePhong.html", error_message=error_message)
        except ValueError:
            error_message = "Định dạng ngày trả không hợp lệ. Vui lòng nhập lại."
            return render_template("update_thuePhong.html", error_message=error_message)

    update_query = """
        UPDATE thuePhong
        SET ngayTra = %s
        WHERE maHD = %s
    """
    data = (ngayTra, maHD)

    try:
        cursor.execute(update_query, data)
        connection.commit()
        message = "Cập nhật dữ liệu thành công"
        return render_template("update_thuePhong.html", message=message)
    except psycopg2.Error as e:
        connection.rollback()
        error_message = f"Lỗi: {e}"
        return render_template("update_thuePhong.html", error_message=error_message)

@app.route("/home/search/khachHang")
def search_khachHang_form():
    return render_template("search_khachHang.html")

@app.route("/home/search/khachHang", methods=["POST"])
def search_khachHang_post():
    maKH = request.form.get("maKH")
    tenKH = request.form.get("tenKH")
    cmnd = request.form.get("cmnd")
    SDT = request.form.get("SDT")

    if maKH == "":
        maKH = None
    if tenKH == "":
        tenKH = None
    if cmnd == "":
        cmnd = None
    if SDT == "":
        SDT = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM khachHang
        WHERE (maKH = %s OR %s IS NULL)
        AND (tenKH = %s OR %s IS NULL)
        AND (cmnd = %s OR %s IS NULL)
        AND (SDT = %s OR %s IS NULL)
    """
    data = (maKH, maKH, tenKH, tenKH, cmnd, cmnd, SDT, SDT)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy khách hàng phù hợp."
        return render_template("search_khachHang.html", message=message)
    else:
        return render_template("search_khachHang.html", result=result)
    
@app.route("/home/search/phong")
def search_phong_form():
    return render_template("search_phong.html")

@app.route("/home/search/phong", methods=["POST"])
def search_phong_post():
    maPhong = request.form.get("maPhong")
    giaPhong = request.form.get("giaPhong")
    trangThai = request.form.get("trangThai")

    if maPhong == "":
        maPhong = None
    if giaPhong == "":
        giaPhong = None
    if trangThai == "":
        trangThai = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM search_phong(%s, %s, %s)
    """
    data = (maPhong, giaPhong, trangThai)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy phòng phù hợp."
        return render_template("search_phong.html", message=message)
    else:
        return render_template("search_phong.html", result=result)

@app.route("/home/search/thietBi")
def search_thietBi_form():
    return render_template("search_thietBi.html")

@app.route("/home/search/thietBi", methods=["POST"])
def search_thietBi_post():
    maTB = request.form.get("maTB")
    tenTB = request.form.get("tenTB")

    if maTB == "":
        maTB = None
    if tenTB == "":
        tenTB = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM khoThietBi
        WHERE (maTB = %s OR %s IS NULL)
        AND (tenTB = %s OR %s IS NULL)
    """
    data = (maTB, maTB, tenTB, tenTB)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy thiết bị phù hợp."
        return render_template("search_thietBi.html", message=message)
    else:
        return render_template("search_thietBi.html", result=result)

@app.route("/home/search/dichVu")
def search_dichVu_form():
    return render_template("search_dichVu.html")

@app.route("/home/search/dichVu", methods=["POST"])
def search_dichVu_post():
    maDV = request.form.get("maDV")
    tenDV = request.form.get("tenDV")

    if maDV == "":
        maDV = None
    if tenDV == "":
        tenDV = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM dichVu
        WHERE (maDV = %s OR %s IS NULL)
        AND (tenDV = %s OR %s IS NULL)
    """
    data = (maDV, maDV, tenDV, tenDV)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy dịch vụ phù hợp."
        return render_template("search_dichVu.html", message=message)
    else:
        return render_template("search_dichVu.html", result=result)

@app.route("/home/search/dienNuoc")
def search_dienNuoc_form():
    return render_template("search_dienNuoc.html")

@app.route("/home/search/dienNuoc", methods=["POST"])
def search_dienNuoc_post():
    maDN = request.form.get("maDN")
    maPhong = request.form.get("maPhong")
    thangSD = request.form.get("thangSD")
    namSD = request.form.get("namSD")

    if maDN == "":
        maDN = None
    if maPhong == "":
        maPhong = None
    if thangSD == "":
        thangSD = None
    if namSD == "":
        namSD = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM dienNuoc
        WHERE (maDN = %s OR %s IS NULL)
        AND (maPhong = %s OR %s IS NULL)
        AND (thangSD = %s OR %s IS NULL)
        AND (namSD = %s OR %s IS NULL)
    """
    data = (maDN, maDN, maPhong, maPhong, thangSD, thangSD, namSD, namSD)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy điện nước phù hợp."
        return render_template("search_dienNuoc.html", message=message)
    else:
        return render_template("search_dienNuoc.html", result=result)

@app.route("/home/search/thuePhong")
def search_thuePhong_form():
    return render_template("search_thuePhong.html")

@app.route("/home/search/thuePhong", methods=["POST"])
def search_thuePhong_post():
    maHD = request.form.get("maHD")
    maKH = request.form.get("maKH")
    maPhong = request.form.get("maPhong")

    if maHD == "":
        maHD = None
    if maKH == "":
        maKH = None
    if maPhong == "":
        maPhong = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM thuePhong
        WHERE (maHD = %s OR %s IS NULL)
        AND (maKH = %s OR %s IS NULL)
        AND (maPhong = %s OR %s IS NULL)
    """
    data = (maHD, maHD, maKH, maKH, maPhong, maPhong)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy thông tin thuê phòng phù hợp."
        return render_template("search_thuePhong.html", message=message)
    else:
        return render_template("search_thuePhong.html", result=result)

@app.route("/home/search/trangBi")
def search_trangBi_form():
    return render_template("search_trangBi.html")

@app.route("/home/search/trangBi", methods=["POST"])
def search_trangBi_post():
    maPhong = request.form.get("maPhong")
    maTB = request.form.get("maTB")

    if maTB == "":
        maTB = None
    if maPhong == "":
        maPhong = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM trangBi
        WHERE (maPhong = %s OR %s IS NULL)
        AND (maTB = %s OR %s IS NULL)
    """
    data = (maPhong, maPhong, maTB, maTB)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy thông tin trang bị phù hợp."
        return render_template("search_trangBi.html", message=message)
    else:
        return render_template("search_trangBi.html", result=result)

@app.route("/home/search/suDungDV")
def search_suDungDV_form():
    return render_template("search_suDungDV.html")

@app.route("/home/search/suDungDV", methods=["POST"])
def search_suDungDV_post():
    maSD = request.form.get("maSD")
    maPhong = request.form.get("maPhong")
    maDV = request.form.get("maDV")
    thangDV = request.form.get("thangDV")
    namDV = request.form.get("namDV")

    if maSD == "":
        maSD = None
    if maDV == "":
        maDV = None
    if maPhong == "":
        maPhong = None
    if thangDV == "":
        thangDV = None
    if namDV == "":
        namDV = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM suDungDV
        WHERE (maSD = %s OR %s IS NULL)
        AND (maPhong = %s OR %s IS NULL)
        AND (maDV = %s OR %s IS NULL)
        AND (thangDV = %s OR %s IS NULL)
        AND (namDV = %s OR %s IS NULL)
    """
    data = (maSD, maSD, maPhong, maPhong, maDV, maDV, thangDV, thangDV, namDV, namDV)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy thông tin sử dụng dịch vụ phù hợp."
        return render_template("search_suDungDV.html", message=message)
    else:
        return render_template("search_suDungDV.html", result=result)
    
@app.route("/home/view/hoaDon")
def view_hoaDon_form():
    return render_template("view_hoaDon.html")

@app.route("/home/view/hoaDon", methods=["POST"])
def view_hoaDon_post():
    maKH = request.form.get("maKH")
    tenKH = request.form.get("tenKH")
    maPhong = request.form.get("maPhong")
    thangNam = request.form.get("thangNam")

    if maKH == "":
        maKH = None
    if maPhong == "":
        maPhong = None
    if tenKH == "":
        tenKH = None
    if thangNam == "":
        thangNam = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM hoaDon
        WHERE (maKH = %s OR %s IS NULL)
        AND (tenKH = %s OR %s IS NULL)
        AND (maPhong = %s OR %s IS NULL)
        AND (thangNam = %s OR %s IS NULL)
    """
    data = (maKH, maKH, tenKH, tenKH, maPhong, maPhong, thangNam, thangNam)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy thông tin sử dụng dịch vụ phù hợp."
        return render_template("view_hoaDon.html", message=message)
    else:
        return render_template("view_hoaDon.html", result=result)

@app.route("/home/view/soLuongTB")
def view_soLuongTB_form():
    return render_template("view_soLuongTB.html")

@app.route("/home/view/soLuongTB", methods=["POST"])
def view_soLuongTB_post():
    maPhong = request.form.get("maPhong")

    if maPhong == "":
        maPhong = None

    cursor = connection.cursor()

    select_query = """
        SELECT *
        FROM tongSoLuongThietBi
        WHERE (maPhong = %s OR %s IS NULL)
    """
    data = (maPhong, maPhong)

    cursor.execute(select_query, data)
    result = cursor.fetchall()

    if not result:
        message = "Không tìm thấy thông tin số lượng thiết bị."
        return render_template("view_soLuongTB.html", message=message)
    else:
        return render_template("view_soLuongTB.html", result=result)


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
